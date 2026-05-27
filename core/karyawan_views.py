"""
core/karyawan_views.py
======================
Views untuk Portal Karyawan VIQUAM (/karyawan/).
Semua view menggunakan KaryawanRequiredMixin dari core.mixins.
"""

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.models import ProtectedError, Sum, Count, Q, F, Value, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView, DeleteView, DetailView,
    ListView, TemplateView, UpdateView, View,
)

from .mixins import KaryawanRequiredMixin, _is_karyawan
from .models import (
    Feedback, Kendaraan, Pelanggan, Pemesanan, DetailPemesanan,
    Produk, Sopir, StokMasuk,
)
from .karyawan_forms import (
    DetailPemesananFormSet,
    KendaraanForm,
    PelangganCreateForm,
    PelangganUpdateForm,
    PemesananForm,
    ProdukForm,
    SopirForm,
    StokMasukForm,
)


# ─────────────────────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────────────────────

def karyawan_login(request):
    """Login khusus Karyawan. Pimpinan yang mencoba login di sini ditolak."""
    if request.user.is_authenticated and _is_karyawan(request.user):
        return redirect('karyawan_dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if not _is_karyawan(user):
                messages.error(
                    request,
                    'Akses ditolak. Akun ini tidak memiliki hak akses ke portal Karyawan.'
                )
            else:
                auth_login(request, user)
                next_url = request.GET.get('next', 'karyawan_dashboard')
                return redirect(next_url)
        else:
            messages.error(request, 'Username atau password salah.')
    else:
        form = AuthenticationForm()

    return render(request, 'karyawan/login.html', {'form': form})


def karyawan_logout(request):
    """Logout Karyawan — hanya POST untuk mencegah CSRF via GET."""
    if request.method == 'POST':
        auth_logout(request)
    return redirect('karyawan_login')


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

class KaryawanDashboardView(KaryawanRequiredMixin, TemplateView):
    template_name = 'karyawan/dashboard.html'

    def get_context_data(self, **kwargs):
        # Hindari get_dashboard_context karena mengandung data finansial sensitif (DRY Violation for Pimpinan only)
        ctx = super().get_context_data(**kwargs)
        
        # Hanya ambil data operasional yang diizinkan untuk Karyawan
        ctx['total_produk']     = Produk.objects.count()
        ctx['stok_habis']       = Produk.objects.filter(stok=0).count()
        ctx['pesanan_diproses'] = Pemesanan.objects.filter(status='Diproses').count()
        ctx['total_pelanggan']  = Pelanggan.objects.count()
        ctx['feedback_baru']    = Feedback.objects.select_related('idPelanggan').order_by('-tanggal')[:5]
        
        # Product Sales Data (Operasional - Tetap diizinkan untuk Karyawan)
        from django.db.models import Sum
        product_sales = DetailPemesanan.objects.filter(
            idPemesanan__status='Selesai'
        ).values('idProduk__namaProduk').annotate(total_sold=Sum('jumlah')).order_by('idProduk__namaProduk')
        
        import json
        ps_labels = [p['idProduk__namaProduk'] for p in product_sales]
        ps_data   = [p['total_sold'] for p in product_sales]
        
        ctx['product_labels_json'] = json.dumps(ps_labels)
        ctx['product_sales_data_json'] = json.dumps(ps_data)
        
        return ctx


# ─────────────────────────────────────────────────────────────────────────────
# CRUD: PRODUK
# ─────────────────────────────────────────────────────────────────────────────

class ProdukListView(KaryawanRequiredMixin, ListView):
    model = Produk
    template_name = 'karyawan/produk/list.html'
    context_object_name = 'produk_list'
    paginate_by = 20

    def get_queryset(self):
        qs = Produk.objects.order_by('namaProduk')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(namaProduk__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


class ProdukCreateView(KaryawanRequiredMixin, CreateView):
    model = Produk
    form_class = ProdukForm
    template_name = 'karyawan/produk/form.html'
    success_url = reverse_lazy('karyawan_produk_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title']   = 'Tambah Produk Baru'
        ctx['submit_label'] = 'Simpan Produk'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, f'Produk "{form.instance.namaProduk}" berhasil ditambahkan.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Terdapat kesalahan pada form. Periksa kembali.')
        return super().form_invalid(form)


class ProdukUpdateView(KaryawanRequiredMixin, UpdateView):
    model = Produk
    form_class = ProdukForm
    template_name = 'karyawan/produk/form.html'
    success_url = reverse_lazy('karyawan_produk_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title']   = f'Edit Produk: {self.object.namaProduk}'
        ctx['submit_label'] = 'Simpan Perubahan'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, f'Produk "{form.instance.namaProduk}" berhasil diperbarui.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Terdapat kesalahan pada form. Periksa kembali.')
        return super().form_invalid(form)


class ProdukDeleteView(KaryawanRequiredMixin, DeleteView):
    model = Produk
    template_name = 'karyawan/produk/confirm_delete.html'
    success_url = reverse_lazy('karyawan_produk_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['target'] = self.object
        return ctx

    def form_valid(self, form):
        nama = self.object.namaProduk
        response = super().form_valid(form)
        messages.success(self.request, f'Produk "{nama}" berhasil dihapus.')
        return response


# ─────────────────────────────────────────────────────────────────────────────
# CRUD: SOPIR
# ─────────────────────────────────────────────────────────────────────────────

class SopirListView(KaryawanRequiredMixin, ListView):
    model = Sopir
    template_name = 'karyawan/sopir/list.html'
    context_object_name = 'sopir_list'
    paginate_by = 20

    def get_queryset(self):
        qs = Sopir.objects.prefetch_related('kendaraan_set').order_by('nama')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(nama__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


class SopirCreateView(KaryawanRequiredMixin, CreateView):
    model = Sopir
    form_class = SopirForm
    template_name = 'karyawan/sopir/form.html'
    success_url = reverse_lazy('karyawan_sopir_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title']   = 'Tambah Sopir Baru'
        ctx['submit_label'] = 'Simpan Sopir'
        return ctx

    def form_valid(self, form):
        # Password wajib diisi saat create — model.save() akan meng-hash-nya
        sopir = form.save(commit=False)
        sopir.password = form.cleaned_data['password']
        sopir.save()
        messages.success(self.request, f'Sopir "{sopir.nama}" berhasil ditambahkan.')
        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, 'Terdapat kesalahan pada form. Periksa kembali.')
        return super().form_invalid(form)


class SopirUpdateView(KaryawanRequiredMixin, UpdateView):
    model = Sopir
    form_class = SopirForm
    template_name = 'karyawan/sopir/form.html'
    success_url = reverse_lazy('karyawan_sopir_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title']   = f'Edit Sopir: {self.object.nama}'
        ctx['submit_label'] = 'Simpan Perubahan'
        return ctx

    def form_valid(self, form):
        sopir = form.save(commit=False)
        new_pw = form.cleaned_data.get('password', '').strip()
        if new_pw:
            # Password baru diisi — hash dan simpan
            sopir.password = new_pw   # model.save() akan meng-hash-nya
        else:
            # Password kosong — pertahankan hash lama
            sopir.password = Sopir.objects.get(pk=sopir.pk).password
        sopir.save()
        messages.success(self.request, f'Sopir "{sopir.nama}" berhasil diperbarui.')
        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, 'Terdapat kesalahan pada form. Periksa kembali.')
        return super().form_invalid(form)


class SopirDeleteView(KaryawanRequiredMixin, DeleteView):
    model = Sopir
    template_name = 'karyawan/sopir/confirm_delete.html'
    success_url = reverse_lazy('karyawan_sopir_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['target'] = self.object
        return ctx

    def form_valid(self, form):
        nama = self.object.nama
        response = super().form_valid(form)
        messages.success(self.request, f'Sopir "{nama}" berhasil dihapus.')
        return response


# ─────────────────────────────────────────────────────────────────────────────
# CRUD: KENDARAAN
# ─────────────────────────────────────────────────────────────────────────────

class KendaraanListView(KaryawanRequiredMixin, ListView):
    model = Kendaraan
    template_name = 'karyawan/kendaraan/list.html'
    context_object_name = 'kendaraan_list'
    paginate_by = 20

    def get_queryset(self):
        qs = Kendaraan.objects.select_related('idSopir').order_by('nama')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(nama__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


class KendaraanCreateView(KaryawanRequiredMixin, CreateView):
    model = Kendaraan
    form_class = KendaraanForm
    template_name = 'karyawan/kendaraan/form.html'
    success_url = reverse_lazy('karyawan_kendaraan_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title']   = 'Tambah Kendaraan Baru'
        ctx['submit_label'] = 'Simpan Kendaraan'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, f'Kendaraan "{form.instance.nama}" berhasil ditambahkan.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Terdapat kesalahan pada form. Periksa kembali.')
        return super().form_invalid(form)


class KendaraanUpdateView(KaryawanRequiredMixin, UpdateView):
    model = Kendaraan
    form_class = KendaraanForm
    template_name = 'karyawan/kendaraan/form.html'
    success_url = reverse_lazy('karyawan_kendaraan_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title']   = f'Edit Kendaraan: {self.object.nama}'
        ctx['submit_label'] = 'Simpan Perubahan'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, f'Kendaraan "{form.instance.nama}" berhasil diperbarui.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Terdapat kesalahan pada form. Periksa kembali.')
        return super().form_invalid(form)


class KendaraanDeleteView(KaryawanRequiredMixin, DeleteView):
    model = Kendaraan
    template_name = 'karyawan/kendaraan/confirm_delete.html'
    success_url = reverse_lazy('karyawan_kendaraan_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['target'] = self.object
        return ctx

    def form_valid(self, form):
        nama = self.object.nama
        response = super().form_valid(form)
        messages.success(self.request, f'Kendaraan "{nama}" berhasil dihapus.')
        return response


# ─────────────────────────────────────────────────────────────────────────────
# CRUD: PELANGGAN
# ─────────────────────────────────────────────────────────────────────────────

class PelangganListView(KaryawanRequiredMixin, ListView):
    model = Pelanggan
    template_name = 'karyawan/pelanggan/list.html'
    context_object_name = 'pelanggan_list'
    paginate_by = 20

    def get_queryset(self):
        qs = Pelanggan.objects.order_by('nama')
        q = self.request.GET.get('q', '').strip()
        if q:
            from django.db.models import Q
            qs = qs.filter(Q(nama__icontains=q) | Q(username__icontains=q) | Q(noWa__icontains=q))
        tipe = self.request.GET.get('tipe', '').strip()
        if tipe == 'langganan':
            qs = qs.filter(isLangganan=True)
        elif tipe == 'umum':
            qs = qs.filter(isLangganan=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q']    = self.request.GET.get('q', '')
        ctx['tipe'] = self.request.GET.get('tipe', '')
        return ctx


class PelangganCreateView(KaryawanRequiredMixin, CreateView):
    model = Pelanggan
    form_class = PelangganCreateForm
    template_name = 'karyawan/pelanggan/form.html'
    success_url = reverse_lazy('karyawan_pelanggan_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title']   = 'Tambah Pelanggan Baru'
        ctx['submit_label'] = 'Simpan Pelanggan'
        return ctx

    def form_valid(self, form):
        # form.save() sudah menangani hashing password via PelangganCreateForm.save()
        pelanggan = form.save()
        messages.success(self.request, f'Pelanggan "{pelanggan.nama}" berhasil ditambahkan.')
        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, 'Terdapat kesalahan pada form. Periksa kembali.')
        return super().form_invalid(form)


class PelangganUpdateView(KaryawanRequiredMixin, UpdateView):
    model = Pelanggan
    form_class = PelangganUpdateForm
    template_name = 'karyawan/pelanggan/form.html'
    success_url = reverse_lazy('karyawan_pelanggan_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title']   = f'Edit Pelanggan: {self.object.nama}'
        ctx['submit_label'] = 'Simpan Perubahan'
        return ctx

    def form_valid(self, form):
        pelanggan = form.save(commit=False)
        new_pw = form.cleaned_data.get('password', '').strip()
        if new_pw:
            # Password baru diisi — simpan raw, model.save() akan meng-hash-nya
            pelanggan.password = new_pw
        else:
            # Password kosong — pertahankan hash lama dari DB
            pelanggan.password = Pelanggan.objects.get(pk=pelanggan.pk).password
        pelanggan.save()
        messages.success(self.request, f'Pelanggan "{pelanggan.nama}" berhasil diperbarui.')
        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, 'Terdapat kesalahan pada form. Periksa kembali.')
        return super().form_invalid(form)


class PelangganDeleteView(KaryawanRequiredMixin, DeleteView):
    model = Pelanggan
    template_name = 'karyawan/pelanggan/confirm_delete.html'
    success_url = reverse_lazy('karyawan_pelanggan_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pelanggan = self.get_object()
        # Ambil query secara langsung dari model Pemesanan untuk akurasi data
        pesanan_terkait = Pemesanan.objects.filter(idPelanggan=pelanggan).order_by('-tanggalPemesanan')
        
        context['pesanan_terkait'] = pesanan_terkait
        context['jumlah_pesanan'] = pesanan_terkait.count()
        context['target'] = pelanggan
        return context

    def form_valid(self, form):
        nama = self.object.nama
        response = super().form_valid(form)
        messages.success(
            self.request, 
            f'Pelanggan "{nama}" berhasil dihapus. Data transaksi terkait telah diononimkan.'
        )
        return response


# ─────────────────────────────────────────────────────────────────────────────
# CRUD: STOK MASUK
# ─────────────────────────────────────────────────────────────────────────────

class StokMasukListView(KaryawanRequiredMixin, ListView):
    model = StokMasuk
    template_name = 'karyawan/stok/list.html'
    context_object_name = 'stok_list'
    paginate_by = 20

    def get_queryset(self):
        qs = StokMasuk.objects.select_related('idProduk').order_by('-tanggal', '-idStok')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(idProduk__namaProduk__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


class StokMasukCreateView(KaryawanRequiredMixin, CreateView):
    model = StokMasuk
    form_class = StokMasukForm
    template_name = 'karyawan/stok/form.html'
    success_url = reverse_lazy('karyawan_stok_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title']   = 'Tambah Stok Masuk'
        ctx['submit_label'] = 'Simpan Stok'
        return ctx

    def form_valid(self, form):
        # model.save() otomatis update stok produk via F() expression
        stok = form.save()
        messages.success(
            self.request,
            f'Stok {stok.idProduk.namaProduk} bertambah {stok.jumlah} unit.'
        )
        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, 'Terdapat kesalahan pada form. Periksa kembali.')
        return super().form_invalid(form)


class StokMasukUpdateView(KaryawanRequiredMixin, UpdateView):
    model = StokMasuk
    form_class = StokMasukForm
    template_name = 'karyawan/stok/form.html'
    success_url = reverse_lazy('karyawan_stok_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title']   = f'Edit Stok Masuk #{self.object.idStok}'
        ctx['submit_label'] = 'Simpan Perubahan'
        return ctx

    def form_valid(self, form):
        # model.save() menghitung perbedaan jumlah dan update stok produk
        stok = form.save()
        messages.success(self.request, f'Data stok masuk #{stok.idStok} berhasil diperbarui.')
        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, 'Terdapat kesalahan pada form. Periksa kembali.')
        return super().form_invalid(form)


class StokMasukDeleteView(KaryawanRequiredMixin, DeleteView):
    model = StokMasuk
    template_name = 'karyawan/stok/confirm_delete.html'
    success_url = reverse_lazy('karyawan_stok_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['target'] = self.object
        return ctx

    def form_valid(self, form):
        # model.delete() otomatis kurangi stok produk
        info = f'#{self.object.idStok} ({self.object.idProduk.namaProduk})'
        response = super().form_valid(form)
        messages.success(self.request, f'Stok masuk {info} berhasil dihapus.')
        return response


# ─────────────────────────────────────────────────────────────────────────────
# FEEDBACK — List, Detail, Delete saja (tidak ada Create dari Karyawan)
# ─────────────────────────────────────────────────────────────────────────────

class FeedbackListView(KaryawanRequiredMixin, ListView):
    model = Feedback
    template_name = 'karyawan/feedback/list.html'
    context_object_name = 'feedback_list'
    paginate_by = 20

    def get_queryset(self):
        qs = Feedback.objects.select_related('idPelanggan').order_by('-tanggal')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(idPelanggan__nama__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


class FeedbackDetailView(KaryawanRequiredMixin, DetailView):
    model = Feedback
    template_name = 'karyawan/feedback/detail.html'
    context_object_name = 'feedback'


class FeedbackDeleteView(KaryawanRequiredMixin, DeleteView):
    model = Feedback
    template_name = 'karyawan/feedback/confirm_delete.html'
    success_url = reverse_lazy('karyawan_feedback_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['target'] = self.object
        return ctx

    def form_valid(self, form):
        info = f'{self.object.idPelanggan.nama}'
        response = super().form_valid(form)
        messages.success(self.request, f'Feedback dari "{info}" berhasil dihapus.')
        return response

# ─────────────────────────────────────────────────────────────────────────────
# PEMESANAN + DETAIL (inlineformset_factory)
#
# Arsitektur:
#   PemesananForm          → header pesanan (1 form)
#   DetailPemesananFormSet → baris produk  (N form, inlineformset)
#
# Keduanya di-render dalam 1 halaman dan di-submit dalam 1 POST.
# Seluruh operasi dibungkus transaction.atomic() agar jika salah satu
# gagal, tidak ada data setengah-jadi yang tersimpan.
# ─────────────────────────────────────────────────────────────────────────────

class PemesananListView(KaryawanRequiredMixin, ListView):
    model = Pemesanan
    template_name = 'karyawan/pemesanan/list.html'
    context_object_name = 'pemesanan_list'
    paginate_by = 20

    def get_queryset(self):
        from django.db.models import Q
        qs = Pemesanan.objects.select_related(
            'idPelanggan', 'idSopir'
        ).order_by('-tanggalPemesanan')

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(idPelanggan__nama__icontains=q) |
                Q(idPemesanan__icontains=q)
            )
        status = self.request.GET.get('status', '').strip()
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q']      = self.request.GET.get('q', '')
        ctx['status'] = self.request.GET.get('status', '')
        ctx['status_choices'] = Pemesanan.STATUS_CHOICES
        return ctx


class PemesananCreateView(KaryawanRequiredMixin, View):
    """
    Create Pemesanan + DetailPemesanan dalam satu halaman.

    Menggunakan View dasar (bukan CreateView) karena kita perlu
    mengelola dua form sekaligus: PemesananForm dan DetailPemesananFormSet.
    """
    template_name = 'karyawan/pemesanan/form.html'

    def _get_formset(self, pemesanan_instance=None, data=None, files=None):
        """Buat formset dengan extra=1 untuk create."""
        from .karyawan_forms import DetailPemesananFormSet
        return DetailPemesananFormSet(
            data=data,
            files=files,
            instance=pemesanan_instance,
            prefix='detail',
        )

    def get(self, request):
        form    = PemesananForm()
        formset = self._get_formset()
        return render(request, self.template_name, {
            'form':         form,
            'formset':      formset,
            'form_title':   'Buat Pesanan Baru',
            'submit_label': 'Simpan Pesanan',
        })

    def post(self, request):
        form = PemesananForm(request.POST, request.FILES)

        # Formset butuh instance sementara untuk validasi FK
        # Kita buat instance dummy dulu, baru simpan jika valid
        formset = self._get_formset(data=request.POST, files=request.FILES)

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    # Simpan header pesanan
                    pemesanan = form.save(commit=False)
                    pemesanan.updated_by = request.user
                    pemesanan.keterangan_admin = (
                        f'{request.user.username} membuat pesanan baru via Portal Karyawan'
                    )
                    pemesanan.save()

                    # Kaitkan formset ke instance yang baru tersimpan
                    formset.instance = pemesanan
                    formset.save()

                    # Hitung ulang total dari semua detail yang tersimpan
                    pemesanan.update_total()

                    # Auto-update status pembayaran berdasarkan nominal
                    pemesanan.update_status_pembayaran()
                    pemesanan.save(update_fields=['total', 'statusPembayaran', 'sisaTagihan'])

                messages.success(
                    request,
                    f'Pesanan #{pemesanan.idPemesanan} berhasil dibuat.'
                )
                return redirect('karyawan_pemesanan_list')
            except Exception as exc:
                messages.error(request, f'Gagal menyimpan pesanan: {exc}')
        else:
            messages.error(request, 'Terdapat kesalahan pada form. Periksa kembali.')

        return render(request, self.template_name, {
            'form':         form,
            'formset':      formset,
            'form_title':   'Buat Pesanan Baru',
            'submit_label': 'Simpan Pesanan',
        })


class PemesananUpdateView(KaryawanRequiredMixin, View):
    """
    Update Pemesanan + DetailPemesanan dalam satu halaman.

    Pola sama dengan Create, tapi form dan formset di-bind ke instance
    yang sudah ada. Formset dengan can_delete=True memungkinkan
    karyawan menghapus baris detail yang tidak diperlukan.
    """
    template_name = 'karyawan/pemesanan/form.html'

    def _get_object(self, pk):
        return get_object_or_404(Pemesanan, pk=pk)

    def _get_formset(self, pemesanan_instance, data=None, files=None):
        from .karyawan_forms import DetailPemesananFormSet
        return DetailPemesananFormSet(
            data=data,
            files=files,
            instance=pemesanan_instance,
            prefix='detail',
        )

    def get(self, request, pk):
        pemesanan = self._get_object(pk)
        form    = PemesananForm(instance=pemesanan)
        formset = self._get_formset(pemesanan)
        return render(request, self.template_name, {
            'form':         form,
            'formset':      formset,
            'pemesanan':    pemesanan,
            'form_title':   f'Edit Pesanan #{pemesanan.idPemesanan}',
            'submit_label': 'Simpan Perubahan',
        })

    def post(self, request, pk):
        pemesanan = self._get_object(pk)
        form    = PemesananForm(request.POST, request.FILES, instance=pemesanan)
        formset = self._get_formset(pemesanan, data=request.POST, files=request.FILES)

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    pemesanan = form.save(commit=False)
                    pemesanan.updated_by = request.user
                    pemesanan.keterangan_admin = (
                        f'{request.user.username} memperbarui pesanan via Portal Karyawan'
                    )
                    pemesanan.save()

                    formset.save()

                    # Hitung ulang total setelah semua detail tersimpan/dihapus
                    pemesanan.update_total()
                    pemesanan.update_status_pembayaran()
                    pemesanan.save(update_fields=['total', 'statusPembayaran', 'sisaTagihan'])

                messages.success(
                    request,
                    f'Pesanan #{pemesanan.idPemesanan} berhasil diperbarui.'
                )
                return redirect('karyawan_pemesanan_list')
            except Exception as exc:
                messages.error(request, f'Gagal menyimpan perubahan: {exc}')
        else:
            messages.error(request, 'Terdapat kesalahan pada form. Periksa kembali.')

        return render(request, self.template_name, {
            'form':         form,
            'formset':      formset,
            'pemesanan':    pemesanan,
            'form_title':   f'Edit Pesanan #{pemesanan.idPemesanan}',
            'submit_label': 'Simpan Perubahan',
        })


class PemesananDeleteView(KaryawanRequiredMixin, DeleteView):
    model = Pemesanan
    template_name = 'karyawan/pemesanan/confirm_delete.html'
    success_url = reverse_lazy('karyawan_pemesanan_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['target'] = self.object
        return ctx

        return response


# ─────────────────────────────────────────────────────────────────────────────
# LAPORAN MANAJEMEN (Karyawan & Pimpinan)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_date_range(request):
    """Utility safe-filter untuk validasi rentang waktu."""
    tgl_mulai = request.GET.get('tgl_mulai')
    tgl_akhir = request.GET.get('tgl_akhir')
    
    start_date = None
    end_date = None
    
    if tgl_mulai:
        try:
            start_date = datetime.strptime(tgl_mulai, '%Y-%m-%d')
        except ValueError:
            pass
            
    if tgl_akhir:
        try:
            end_date = datetime.strptime(tgl_akhir, '%Y-%m-%d')
        except ValueError:
            pass
            
    return start_date, end_date, tgl_mulai, tgl_akhir


def laporan_pelanggan(request):
    """View Laporan Pelanggan dengan agregasi transaksi."""
    start_date, end_date, tgl_mulai, tgl_akhir = _parse_date_range(request)
    
    # Base Queryset
    pelanggan_qs = Pelanggan.objects.all()
    
    # Filter by Date (Pemesanan date)
    if start_date or end_date:
        order_filter = Q()
        if start_date:
            order_filter &= Q(pemesanan__tanggalPemesanan__gte=start_date)
        if end_date:
            order_filter &= Q(pemesanan__tanggalPemesanan__lte=end_date)
            
        pelanggan_qs = pelanggan_qs.annotate(
            jml_transaksi=Count('pemesanan', filter=order_filter),
            total_pembelian=Coalesce(Sum('pemesanan__total', filter=order_filter), Value(0), output_field=DecimalField())
        )
    else:
        pelanggan_qs = pelanggan_qs.annotate(
            jml_transaksi=Count('pemesanan'),
            total_pembelian=Coalesce(Sum('pemesanan__total'), Value(0), output_field=DecimalField())
        )
        
    return render(request, 'core/laporan_pelanggan.html', {
        'pelanggan_list': pelanggan_qs.order_by('-total_pembelian'),
        'tgl_mulai': tgl_mulai,
        'tgl_akhir': tgl_akhir,
        'active_menu': 'laporan_pelanggan'
    })


def laporan_produk(request):
    """View Laporan Produk dengan total kuantitas terjual."""
    start_date, end_date, tgl_mulai, tgl_akhir = _parse_date_range(request)
    
    produk_qs = Produk.objects.all()
    
    # Filter agregasi terjual berdasarkan status pesanan 'Selesai'
    base_filter = Q(detailpemesanan__idPemesanan__status='Selesai')
    if start_date:
        base_filter &= Q(detailpemesanan__idPemesanan__tanggalPemesanan__gte=start_date)
    if end_date:
        base_filter &= Q(detailpemesanan__idPemesanan__tanggalPemesanan__lte=end_date)
        
    produk_qs = produk_qs.annotate(
        total_terjual=Coalesce(Sum('detailpemesanan__jumlah', filter=base_filter), Value(0))
    ).order_by('-total_terjual')
    
    return render(request, 'core/laporan_produk.html', {
        'produk_list': produk_qs,
        'tgl_mulai': tgl_mulai,
        'tgl_akhir': tgl_akhir,
        'active_menu': 'laporan_produk'
    })


def laporan_pemesanan_pendapatan(request):
    """View Laporan Transaksi Pemesanan dan Pendapatan."""
    start_date, end_date, tgl_mulai, tgl_akhir = _parse_date_range(request)
    
    # select_related untuk mencegah N+1 query pada Pelanggan
    pesanan_qs = Pemesanan.objects.select_related('idPelanggan').all().order_by('-tanggalPemesanan')
    
    if start_date:
        pesanan_qs = pesanan_qs.filter(tanggalPemesanan__gte=start_date)
    if end_date:
        pesanan_qs = pesanan_qs.filter(tanggalPemesanan__lte=end_date)
        
    # Agregasi Total Pendapatan dari Queryset saat ini
    total_pendapatan = pesanan_qs.filter(status='Selesai').aggregate(
        total=Coalesce(Sum('total'), Value(0), output_field=DecimalField())
    )['total']
    
    return render(request, 'core/laporan_pemesanan_pendapatan.html', {
        'pesanan_list': pesanan_qs,
        'total_pendapatan': total_pendapatan,
        'tgl_mulai': tgl_mulai,
        'tgl_akhir': tgl_akhir,
        'active_menu': 'laporan_pemesanan'
    })


def laporan_sopir_kendaraan(request):
    """View Laporan Performa Sopir danutilitas Kendaraan."""
    start_date, end_date, tgl_mulai, tgl_akhir = _parse_date_range(request)
    
    sopir_qs = Sopir.objects.all()
    
    order_filter = Q(pemesanan__status='Selesai')
    if start_date:
        order_filter &= Q(pemesanan__tanggalPemesanan__gte=start_date)
    if end_date:
        order_filter &= Q(pemesanan__tanggalPemesanan__lte=end_date)
        
    sopir_qs = sopir_qs.annotate(
        total_pengiriman=Count('pemesanan', filter=order_filter)
    ).order_by('-total_pengiriman')
    
    return render(request, 'core/laporan_sopir_kendaraan.html', {
        'sopir_list': sopir_qs,
        'tgl_mulai': tgl_mulai,
        'tgl_akhir': tgl_akhir,
        'active_menu': 'laporan_sopir'
    })


def laporan_feedback(request):
    """View Laporan Feedback Pelanggan."""
    start_date, end_date, tgl_mulai, tgl_akhir = _parse_date_range(request)
    
    feedback_qs = Feedback.objects.select_related('idPelanggan').all().order_by('-tanggal')
    
    if start_date:
        feedback_qs = feedback_qs.filter(tanggal__gte=start_date)
    if end_date:
        feedback_qs = feedback_qs.filter(tanggal__lte=end_date)
        
    return render(request, 'core/laporan_feedback.html', {
        'feedback_list': feedback_qs,
        'tgl_mulai': tgl_mulai,
        'tgl_akhir': tgl_akhir,
        'active_menu': 'laporan_feedback'
    })

