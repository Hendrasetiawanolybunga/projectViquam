"""
core/pimpinan_forms.py
======================
Form-form untuk Portal Pimpinan — manajemen akun Karyawan.
"""

from django import forms
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm
from django.contrib.auth.models import User

CSS = 'form-control'

# Pilihan jabatan yang tersedia.
# Setiap jabatan akan dipetakan ke Django Group dengan nama yang sama.
# Tambahkan pilihan baru di sini tanpa mengubah view.
JABATAN_CHOICES = [
    ('',               '— Pilih Jabatan —'),
    ('Admin Gudang',   'Admin Gudang'),
    ('Kasir',          'Kasir'),
    ('CS',             'Customer Service (CS)'),
    ('Admin Umum',     'Admin Umum'),
]


class KaryawanAccountCreateForm(UserCreationForm):
    """
    Form buat akun Karyawan baru oleh Pimpinan.

    Menggunakan UserCreationForm sehingga:
    - Validasi kekuatan password (AUTH_PASSWORD_VALIDATORS) aktif
    - Password di-hash Django — tidak pernah plain-text

    Field 'jabatan' dipetakan ke Django Group di form_valid() view.
    Field 'is_staff' dan 'is_superuser' TIDAK diekspos — di-set paksa di view.
    """

    first_name = forms.CharField(
        label='Nama Depan', max_length=30, required=False,
        widget=forms.TextInput(attrs={'class': CSS}),
    )
    last_name = forms.CharField(
        label='Nama Belakang', max_length=150, required=False,
        widget=forms.TextInput(attrs={'class': CSS}),
    )
    email = forms.EmailField(
        label='Email', required=False,
        widget=forms.EmailInput(attrs={'class': CSS}),
    )
    jabatan = forms.ChoiceField(
        label='Jabatan',
        choices=JABATAN_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Jabatan menentukan Group akses yang diberikan secara otomatis.',
    )

    class Meta:
        model  = User
        # is_staff, is_superuser, groups, user_permissions sengaja tidak ada
        # di sini — mencegah privilege escalation via form tampering
        fields = ('username', 'first_name', 'last_name', 'email',
                  'jabatan', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': CSS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': CSS})
        self.fields['password2'].widget.attrs.update({'class': CSS})
        self.fields['password1'].label = 'Password'
        self.fields['password2'].label = 'Konfirmasi Password'


class KaryawanAccountUpdateForm(forms.ModelForm):
    """
    Form edit akun Karyawan (username, nama, email, is_active, jabatan).
    Password TIDAK ada — reset password ditangani KaryawanPasswordResetView.

    SECURITY: is_staff, is_superuser, groups, user_permissions tidak diekspos.
    """

    jabatan = forms.ChoiceField(
        label='Jabatan',
        choices=JABATAN_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Mengubah jabatan akan memperbarui Group akses secara otomatis.',
    )
    is_active = forms.BooleanField(
        label='Akun Aktif',
        required=False,
        help_text='Nonaktifkan untuk memblokir login tanpa menghapus akun.',
    )

    class Meta:
        model  = User
        fields = ('username', 'first_name', 'last_name', 'email', 'is_active', 'jabatan')
        widgets = {
            'username':   forms.TextInput(attrs={'class': CSS}),
            'first_name': forms.TextInput(attrs={'class': CSS}),
            'last_name':  forms.TextInput(attrs={'class': CSS}),
            'email':      forms.EmailInput(attrs={'class': CSS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Isi jabatan awal dari group yang dimiliki user (selain 'Karyawan')
        if self.instance and self.instance.pk:
            jabatan_saat_ini = (
                self.instance.groups
                .exclude(name='Karyawan')
                .values_list('name', flat=True)
                .first()
            )
            if jabatan_saat_ini:
                self.initial['jabatan'] = jabatan_saat_ini


class KaryawanPasswordResetForm(SetPasswordForm):
    """
    Form reset password Karyawan oleh Pimpinan.
    Mewarisi SetPasswordForm — AUTH_PASSWORD_VALIDATORS tetap aktif.
    """

    new_password1 = forms.CharField(
        label='Password Baru',
        widget=forms.PasswordInput(attrs={'class': CSS, 'autocomplete': 'new-password'}),
        strip=False,
        help_text='Minimal 8 karakter. Tidak boleh terlalu umum.',
    )
    new_password2 = forms.CharField(
        label='Konfirmasi Password Baru',
        widget=forms.PasswordInput(attrs={'class': CSS, 'autocomplete': 'new-password'}),
        strip=False,
    )
