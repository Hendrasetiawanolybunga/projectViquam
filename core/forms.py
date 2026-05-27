from django import forms
from decimal import Decimal
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.core.validators import RegexValidator
from .models import Pelanggan, Pemesanan, Sopir

phone_validator = RegexValidator(
    regex=r'^\d+$',
    message='Nomor WhatsApp hanya boleh berisi angka.'
)

class SopirEditPengirimanForm(forms.ModelForm):
    keterangan = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control bg-white text-dark border-dark',
            'placeholder': 'Tambahkan keterangan (opsional)',
            'rows': 3
        }),
        required=False,
        label='Keterangan'
    )
    
    class Meta:
        model = Pemesanan
        fields = ['status', 'fotoPengiriman']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control bg-white text-dark border-dark'}),
            'fotoPengiriman': forms.FileInput(attrs={'class': 'form-control-file bg-white text-dark border-dark'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit status choices to only 'Selesai' and 'Dibatalkan'
        self.fields['status'].choices = [
            ('Selesai', 'Selesai'),
            ('Dibatalkan', 'Dibatalkan')
        ]

class PelangganRegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control bg-white text-dark border-dark',
        'placeholder': 'Masukkan password'
    }))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control bg-white text-dark border-dark',
        'placeholder': 'Konfirmasi password'
    }))
    noWa = forms.CharField(
        validators=[phone_validator],
        widget=forms.TextInput(attrs={
            'class': 'form-control bg-white text-dark border-dark',
            'placeholder': 'Nomor WhatsApp',
            'pattern': '[0-9]+',
            'inputmode': 'numeric'
        })
    )
    
    class Meta:
        model = Pelanggan
        fields = ['nama', 'noWa', 'alamat', 'latitude', 'longitude', 'username', 'password']
        widgets = {
            'nama': forms.TextInput(attrs={'class': 'form-control bg-white text-dark border-dark', 'placeholder': 'Nama lengkap'}),
            'noWa': forms.TextInput(attrs={'class': 'form-control bg-white text-dark border-dark', 'placeholder': 'Nomor WhatsApp', 'pattern': '[0-9]+', 'inputmode': 'numeric'}),
            'alamat': forms.Textarea(attrs={'class': 'form-control bg-white text-dark border-dark', 'placeholder': 'Detail alamat (Blok/No Rumah)', 'rows': 2}),
            'username': forms.TextInput(attrs={'class': 'form-control bg-white text-dark border-dark', 'placeholder': 'Username'}),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
        }
    
    def clean_confirm_password(self):
        password = self.cleaned_data.get('password')
        confirm_password = self.cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Password tidak cocok!")
        return confirm_password
    
    def save(self, commit=True):
        pelanggan = super().save(commit=False)
        # Biarkan raw password ada di pelanggan.password
        # Model akan menghashnya saat pelanggan.save() dipanggil
        if commit:
            pelanggan.save()
        return pelanggan

class PelangganLoginForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control bg-white text-dark border-dark',
        'placeholder': 'Username'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control bg-white text-dark border-dark',
        'placeholder': 'Password'
    }))

class PemesananCheckoutForm(forms.ModelForm):
    class Meta:
        model = Pemesanan
        fields = ['latitude', 'longitude', 'alamatPengiriman', 'buktiBayar', 'jenisPembayaran']
        widgets = {
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'alamatPengiriman': forms.Textarea(attrs={
                'class': 'form-control bg-white text-dark border-dark', 
                'placeholder': 'Detail alamat pengiriman (Blok/No Rumah)',
                'rows': 2
            }),
            'buktiBayar': forms.FileInput(attrs={
                'class': 'form-control-file bg-white text-dark border-dark',
            }),
            'jenisPembayaran': forms.Select(attrs={
                'class': 'form-control bg-white text-dark border-dark',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.is_langganan = kwargs.pop('is_langganan', False)
        super().__init__(*args, **kwargs)
        
        # Jika bukan pelanggan langganan, hide field pembayaran advanced
        if not self.is_langganan:
            self.fields['jenisPembayaran'].widget = forms.HiddenInput()
            # Set required=False untuk general customers
            self.fields['jenisPembayaran'].required = False
            # Set default values for general customers
            self.initial['jenisPembayaran'] = 'Transfer'
        else:
            # Pelanggan langganan bisa memilih jenis pembayaran
            self.fields['jenisPembayaran'].required = True
        
        # Bukti bayar akan di-set required/not required di clean_buktiBayar berdasarkan jenis pembayaran
    
    def clean_buktiBayar(self):
        buktiBayar = self.cleaned_data.get('buktiBayar')
        jenisPembayaran = self.cleaned_data.get('jenisPembayaran')
        
        # Validasi bukti bayar berdasarkan jenis pembayaran
        if self.is_langganan:
            if jenisPembayaran == 'Transfer' and not buktiBayar:
                raise forms.ValidationError('Bukti pembayaran wajib diupload untuk pembayaran Transfer.')
            elif jenisPembayaran in ['COD', 'Piutang']:
                # COD dan Piutang tidak memerlukan bukti bayar
                pass
        else:
            # Pelanggan umum WAJIB upload bukti bayar
            if not buktiBayar:
                raise forms.ValidationError('Bukti pembayaran wajib diupload.')
        
        return buktiBayar
    
    def clean_nominalDibayar(self):
        nominalDibayar = self.cleaned_data.get('nominalDibayar')
        jenisPembayaran = self.cleaned_data.get('jenisPembayaran')
        
        if self.is_langganan and jenisPembayaran == 'DP':
            if nominalDibayar is None or nominalDibayar <= 0:
                raise forms.ValidationError('Nominal DP harus lebih dari 0 untuk pembayaran DP.')
        
        return nominalDibayar
    
    def clean(self):
        cleaned_data = super().clean()
        
        if self.is_langganan:
            jenisPembayaran = cleaned_data.get('jenisPembayaran')
            
            # Tidak ada validasi nominal untuk flow baru
        else:
            # Force consistent values for general customers
            cleaned_data['jenisPembayaran'] = 'Transfer'
            # Sync to instance to prevent model validation issues
            self.instance.jenisPembayaran = 'Transfer'
            self.instance.nominalDibayar = Decimal('0.00')
            self.instance.sisaTagihan = Decimal('0.00')
            self.instance.statusPembayaran = 'Lunas'
        
        return cleaned_data

class PelangganUpdateForm(forms.ModelForm):
    noWa = forms.CharField(
        validators=[phone_validator],
        widget=forms.TextInput(attrs={
            'class': 'form-control bg-white text-dark border-dark',
            'pattern': '[0-9]+',
            'inputmode': 'numeric'
        })
    )

    class Meta:
        model = Pelanggan
        fields = ['nama', 'noWa', 'alamat', 'latitude', 'longitude']
        widgets = {
            'nama': forms.TextInput(attrs={'class': 'form-control bg-white text-dark border-dark'}),
            'alamat': forms.Textarea(attrs={'class': 'form-control bg-white text-dark border-dark', 'rows': 3}),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
        }

class ChangePasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label="Password baru",
        widget=forms.PasswordInput(attrs={'class': 'form-control bg-white text-dark border-dark'}),
        strip=False,
    )
    new_password2 = forms.CharField(
        label="Konfirmasi password baru",
        widget=forms.PasswordInput(attrs={'class': 'form-control bg-white text-dark border-dark'}),
        strip=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
# STAFF USER MANAGEMENT — digunakan oleh Portal Pimpinan (/pimpinan/users/)
# ─────────────────────────────────────────────────────────────────────────────

CSS = 'form-control'  # shorthand untuk widget attrs


class StaffUserCreateForm(UserCreationForm):
    """
    Form untuk membuat akun staff baru oleh Pimpinan.

    Menggunakan UserCreationForm bawaan Django sehingga:
    - Validasi kekuatan password (AUTH_PASSWORD_VALIDATORS) tetap berjalan.
    - Password di-hash oleh Django sebelum disimpan — tidak pernah plain-text.

    Field 'is_staff' TIDAK diekspos ke form; nilainya di-set paksa ke True
    di dalam view (form_valid) agar Pimpinan tidak bisa memanipulasinya.
    """

    first_name = forms.CharField(
        label='Nama Depan',
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={'class': CSS, 'placeholder': 'Nama depan (opsional)'}),
    )
    last_name = forms.CharField(
        label='Nama Belakang',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': CSS, 'placeholder': 'Nama belakang (opsional)'}),
    )
    email = forms.EmailField(
        label='Email',
        required=False,
        widget=forms.EmailInput(attrs={'class': CSS, 'placeholder': 'email@contoh.com'}),
    )

    class Meta:
        model = User
        # Hanya field yang aman untuk diisi oleh Pimpinan.
        # 'is_staff', 'is_superuser', 'groups', 'user_permissions' sengaja
        # TIDAK ada di sini — mencegah privilege escalation via form tampering.
        fields = ('username', 'first_name', 'last_name', 'email',
                  'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': CSS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Terapkan CSS class ke field password bawaan UserCreationForm
        self.fields['password1'].widget.attrs.update({'class': CSS})
        self.fields['password2'].widget.attrs.update({'class': CSS})
        self.fields['password1'].label = 'Password'
        self.fields['password2'].label = 'Konfirmasi Password'


class StaffUserUpdateForm(forms.ModelForm):
    """
    Form untuk memperbarui data akun staff oleh Pimpinan.

    Desain keamanan:
    - Password TIDAK ada di form ini. Reset password ditangani oleh
      endpoint terpisah (StaffUserPasswordResetView) menggunakan
      SetPasswordForm — ini mencegah hash password yang valid
      tertimpa string kosong secara tidak sengaja.
    - Field 'is_staff', 'is_superuser', 'groups', 'user_permissions'
      sengaja dikecualikan untuk mencegah privilege escalation.
    - Field 'is_active' diekspos agar Pimpinan bisa menonaktifkan
      akun tanpa harus menghapusnya (soft-disable).
    """

    first_name = forms.CharField(
        label='Nama Depan',
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={'class': CSS}),
    )
    last_name = forms.CharField(
        label='Nama Belakang',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': CSS}),
    )
    email = forms.EmailField(
        label='Email',
        required=False,
        widget=forms.EmailInput(attrs={'class': CSS}),
    )
    is_active = forms.BooleanField(
        label='Akun Aktif',
        required=False,
        help_text='Nonaktifkan untuk memblokir login tanpa menghapus akun.',
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'is_active')
        widgets = {
            'username': forms.TextInput(attrs={'class': CSS}),
        }


class StaffUserPasswordResetForm(SetPasswordForm):
    """
    Form reset password staff oleh Pimpinan.

    Mewarisi SetPasswordForm Django sehingga:
    - Validasi AUTH_PASSWORD_VALIDATORS tetap aktif.
    - Password di-hash oleh Django — tidak pernah disimpan plain-text.
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