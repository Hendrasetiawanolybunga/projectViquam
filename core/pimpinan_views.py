"""
core/pimpinan_views.py
======================
Views manajemen akun Karyawan untuk Portal Pimpinan.

Tanggung jawab file ini:
  - KaryawanAccountListView   : daftar akun karyawan yang dikelola Pimpinan
  - KaryawanAccountCreateView : buat akun baru + set Group 'Karyawan' otomatis
  - KaryawanAccountUpdateView : edit data akun (tanpa password)
  - KaryawanAccountDeleteView : hapus akun
  - KaryawanPasswordResetView : reset password akun karyawan

Semua view menggunakan PimpinanRequiredMixin dari core.mixins.
Queryset dibatasi ke akun dengan is_staff=True, is_superuser=False,
dan tergabung dalam Group 'Karyawan' — Pimpinan tidak bisa menyentuh
akun superuser atau sesama Pimpinan.
"""

from django.contrib import messages
from django.contrib.auth.models import Group, User
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .mixins import PimpinanRequiredMixin
from .pimpinan_forms import (
    KaryawanAccountCreateForm,
    KaryawanAccountUpdateForm,
    KaryawanPasswordResetForm,
)


# ─────────────────────────────────────────────────────────────────────────────
# Queryset sentinel — satu definisi, dipakai di semua view
# ─────────────────────────────────────────────────────────────────────────────

def _karyawan_qs():
    """
    Kembalikan queryset User yang boleh dikelola Pimpinan:
      - is_staff=True        : akun staff (bukan pelanggan biasa)
      - is_superuser=False   : bukan superuser
      - group='Karyawan'     : hanya akun karyawan operasional

    Pimpinan dan superuser tidak pernah masuk queryset ini.
    """
    return (
        User.objects
        .filter(is_staff=True, is_superuser=False, groups__name='Karyawan')
        .order_by('username')
    )


# ─────────────────────────────────────────────────────────────────────────────
# LIST
# ─────────────────────────────────────────────────────────────────────────────

class KaryawanAccountListView(PimpinanRequiredMixin, ListView):
    model = User
    template_name = 'pimpinan/karyawan/list.html'
    context_object_name = 'karyawan_list'
    paginate_by = 20

    def get_queryset(self):
        qs = _karyawan_qs()
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(username__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(email__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


# ─────────────────────────────────────────────────────────────────────────────
# CREATE
# ─────────────────────────────────────────────────────────────────────────────

class KaryawanAccountCreateView(PimpinanRequiredMixin, CreateView):
    """
    Buat akun Karyawan baru.

    Logika krusial di form_valid():
    1. is_staff=True      → akun bisa login ke Django admin jika diperlukan
    2. is_superuser=False → tidak boleh jadi superuser (paksa, tidak bisa di-override form)
    3. Group 'Karyawan'   → ditambahkan otomatis berdasarkan field 'jabatan' di form
    4. Password di-hash oleh UserCreationForm — tidak pernah plain-text
    """
    model = User
    form_class = KaryawanAccountCreateForm
    template_name = 'pimpinan/karyawan/form.html'
    success_url = reverse_lazy('pimpinan_karyawan_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title']   = 'Tambah Akun Karyawan'
        ctx['submit_label'] = 'Simpan Akun'
        return ctx

    def form_valid(self, form):
        # commit=False: objek User di memori, belum INSERT ke DB
        user = form.save(commit=False)

        # SECURITY: paksa flag ini terlepas dari isi POST body
        user.is_staff     = True   # wajib agar bisa login ke admin jika perlu
        user.is_superuser = False  # tidak boleh jadi superuser

        user.save()

        # Tambahkan ke Group 'Karyawan' — selalu, tanpa pengecualian
        karyawan_group, _ = Group.objects.get_or_create(name='Karyawan')
        user.groups.add(karyawan_group)

        # Jika form memiliki field 'jabatan', tambahkan ke group jabatan juga
        jabatan = form.cleaned_data.get('jabatan', '').strip()
        if jabatan:
            jabatan_group, _ = Group.objects.get_or_create(name=jabatan)
            user.groups.add(jabatan_group)

        messages.success(
            self.request,
            f'Akun karyawan "{user.username}" berhasil dibuat'
            + (f' dengan jabatan {jabatan}.' if jabatan else '.')
        )
        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, 'Terdapat kesalahan pada form. Periksa kembali.')
        return super().form_invalid(form)


# ─────────────────────────────────────────────────────────────────────────────
# UPDATE
# ─────────────────────────────────────────────────────────────────────────────

class KaryawanAccountUpdateView(PimpinanRequiredMixin, UpdateView):
    """
    Edit data akun Karyawan (username, nama, email, is_active, jabatan).
    Password tidak ada di form ini — gunakan KaryawanPasswordResetView.

    SECURITY — ID Hijacking Prevention:
    get_queryset() dibatasi ke _karyawan_qs() sehingga URL
    /pimpinan/karyawan/<pk>/edit/ dengan pk superuser → 404.
    """
    model = User
    form_class = KaryawanAccountUpdateForm
    template_name = 'pimpinan/karyawan/form.html'
    success_url = reverse_lazy('pimpinan_karyawan_list')

    def get_queryset(self):
        # SECURITY: batasi queryset — superuser/Pimpinan tidak bisa di-edit
        return _karyawan_qs()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title']   = f'Edit Akun: {self.object.username}'
        ctx['submit_label'] = 'Simpan Perubahan'
        ctx['target_user']  = self.object
        return ctx

    def form_valid(self, form):
        user = form.save(commit=False)

        # SECURITY: paksa flag — tidak bisa di-downgrade/upgrade via form
        user.is_staff     = True
        user.is_superuser = False
        user.save()

        # Update jabatan jika diubah
        jabatan = form.cleaned_data.get('jabatan', '').strip()
        if jabatan:
            # Hapus semua group jabatan lama (selain 'Karyawan')
            jabatan_groups = user.groups.exclude(name='Karyawan')
            user.groups.remove(*jabatan_groups)

            # Tambahkan group jabatan baru
            jabatan_group, _ = Group.objects.get_or_create(name=jabatan)
            user.groups.add(jabatan_group)

            # Pastikan tetap di group 'Karyawan'
            karyawan_group, _ = Group.objects.get_or_create(name='Karyawan')
            user.groups.add(karyawan_group)

        messages.success(
            self.request,
            f'Akun "{user.username}" berhasil diperbarui.'
        )
        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, 'Terdapat kesalahan pada form. Periksa kembali.')
        return super().form_invalid(form)


# ─────────────────────────────────────────────────────────────────────────────
# DELETE
# ─────────────────────────────────────────────────────────────────────────────

class KaryawanAccountDeleteView(PimpinanRequiredMixin, DeleteView):
    """
    Hapus akun Karyawan.

    SECURITY: get_queryset() dibatasi ke _karyawan_qs().
    Superuser tidak bisa dihapus via URL ini.
    """
    model = User
    template_name = 'pimpinan/karyawan/confirm_delete.html'
    success_url = reverse_lazy('pimpinan_karyawan_list')

    def get_queryset(self):
        return _karyawan_qs()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['target_user'] = self.object
        return ctx

    def form_valid(self, form):
        username = self.object.username
        response = super().form_valid(form)
        messages.success(self.request, f'Akun "{username}" berhasil dihapus.')
        return response


# ─────────────────────────────────────────────────────────────────────────────
# RESET PASSWORD
# ─────────────────────────────────────────────────────────────────────────────

class KaryawanPasswordResetView(PimpinanRequiredMixin, UpdateView):
    """
    Reset password akun Karyawan oleh Pimpinan.

    Menggunakan KaryawanPasswordResetForm (extends SetPasswordForm) sehingga:
    - AUTH_PASSWORD_VALIDATORS tetap aktif
    - Password di-hash Django — tidak pernah plain-text
    - Hash lama tidak tertimpa string kosong

    SECURITY: get_queryset() dibatasi ke _karyawan_qs().
    """
    model = User
    template_name = 'pimpinan/karyawan/password_reset.html'
    success_url = reverse_lazy('pimpinan_karyawan_list')

    def get_queryset(self):
        return _karyawan_qs()

    def get_form(self, form_class=None):
        """
        Override: SetPasswordForm menerima 'user' sebagai arg pertama,
        bukan 'instance' seperti ModelForm biasa.
        """
        kwargs = self.get_form_kwargs()
        kwargs.pop('instance', None)  # buang 'instance' — SetPasswordForm tidak mengenalnya
        return KaryawanPasswordResetForm(user=self.object, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title']   = f'Reset Password: {self.object.username}'
        ctx['submit_label'] = 'Simpan Password Baru'
        ctx['target_user']  = self.object
        return ctx

    def form_valid(self, form):
        form.save()  # SetPasswordForm.save() menangani hashing
        messages.success(
            self.request,
            f'Password akun "{self.object.username}" berhasil direset.'
        )
        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, 'Password tidak valid. Periksa kembali.')
        return super().form_invalid(form)
