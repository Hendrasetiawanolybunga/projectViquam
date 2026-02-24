from django import forms
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.hashers import make_password
from .models import Pelanggan, Pemesanan, Sopir, Provinsi, Kabupaten, Kecamatan, Kelurahan

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
    # Chained dropdown fields for region selection
    provinsi = forms.ModelChoiceField(
        queryset=Provinsi.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control bg-white text-dark border-dark', 'id': 'id_provinsi'}),
        label='Provinsi'
    )
    kabupaten = forms.ModelChoiceField(
        queryset=Kabupaten.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control bg-white text-dark border-dark', 'id': 'id_kabupaten'}),
        label='Kabupaten/Kota'
    )
    kecamatan = forms.ModelChoiceField(
        queryset=Kecamatan.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control bg-white text-dark border-dark', 'id': 'id_kecamatan'}),
        label='Kecamatan'
    )
    
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
        fields = ['nama', 'noWa', 'idKelurahan', 'alamat', 'username', 'password']
        widgets = {
            'nama': forms.TextInput(attrs={'class': 'form-control bg-white text-dark border-dark', 'placeholder': 'Nama lengkap'}),
            'noWa': forms.TextInput(attrs={'class': 'form-control bg-white text-dark border-dark', 'placeholder': 'Nomor WhatsApp'}),
            'idKelurahan': forms.Select(attrs={'class': 'form-control bg-white text-dark border-dark', 'id': 'id_idKelurahan'}),
            'alamat': forms.Textarea(attrs={'class': 'form-control bg-white text-dark border-dark', 'placeholder': 'Detail alamat (Blok/No Rumah)', 'rows': 2}),
            'username': forms.TextInput(attrs={'class': 'form-control bg-white text-dark border-dark', 'placeholder': 'Username'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Provinsi, Kabupaten, Kecamatan, Kelurahan
        
        # Initialize querysets
        self.fields['provinsi'].queryset = Provinsi.objects.all()
        self.fields['kabupaten'].queryset = Kabupaten.objects.none()
        self.fields['kecamatan'].queryset = Kecamatan.objects.none()
        self.fields['idKelurahan'].queryset = Kelurahan.objects.none()
        
        # If editing existing pelanggan with kelurahan
        if self.instance.pk and self.instance.idKelurahan:
            kelurahan = self.instance.idKelurahan
            kecamatan = kelurahan.kecamatan
            kabupaten = kecamatan.kabupaten
            provinsi = kabupaten.provinsi
            
            self.fields['kabupaten'].queryset = Kabupaten.objects.filter(provinsi=provinsi)
            self.fields['kecamatan'].queryset = Kecamatan.objects.filter(kabupaten=kabupaten)
            self.fields['idKelurahan'].queryset = Kelurahan.objects.filter(kecamatan=kecamatan)
            
            self.fields['provinsi'].initial = provinsi
            self.fields['kabupaten'].initial = kabupaten
            self.fields['kecamatan'].initial = kecamatan
    
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
        fields = ['idKelurahanPengiriman', 'alamatPengiriman', 'buktiBayar']
        widgets = {
            'idKelurahanPengiriman': forms.Select(attrs={
                'class': 'form-control bg-white text-dark border-dark',
                'id': 'id_idKelurahanPengiriman'
            }),
            'alamatPengiriman': forms.Textarea(attrs={
                'class': 'form-control bg-white text-dark border-dark', 
                'placeholder': 'Detail alamat pengiriman (Blok/No Rumah)',
                'rows': 2
            }),
            'buktiBayar': forms.FileInput(attrs={
                'class': 'form-control-file bg-white text-dark border-dark',
                'required': True
            }),
        }

class PelangganUpdateForm(forms.ModelForm):
    class Meta:
        model = Pelanggan
        fields = ['nama', 'noWa', 'alamat']
        widgets = {
            'nama': forms.TextInput(attrs={'class': 'form-control bg-white text-dark border-dark'}),
            'noWa': forms.TextInput(attrs={'class': 'form-control bg-white text-dark border-dark'}),
            'alamat': forms.Textarea(attrs={'class': 'form-control bg-white text-dark border-dark', 'rows': 3}),
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