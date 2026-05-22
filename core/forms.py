from django import forms
from decimal import Decimal
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.hashers import make_password
from .models import Pelanggan, Pemesanan, Sopir

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
    
    class Meta:
        model = Pelanggan
        fields = ['nama', 'noWa', 'alamat', 'latitude', 'longitude', 'username', 'password']
        widgets = {
            'nama': forms.TextInput(attrs={'class': 'form-control bg-white text-dark border-dark', 'placeholder': 'Nama lengkap'}),
            'noWa': forms.TextInput(attrs={'class': 'form-control bg-white text-dark border-dark', 'placeholder': 'Nomor WhatsApp'}),
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
    class Meta:
        model = Pelanggan
        fields = ['nama', 'noWa', 'alamat', 'latitude', 'longitude']
        widgets = {
            'nama': forms.TextInput(attrs={'class': 'form-control bg-white text-dark border-dark'}),
            'noWa': forms.TextInput(attrs={'class': 'form-control bg-white text-dark border-dark'}),
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