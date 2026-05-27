"""
core/karyawan_forms.py
======================
Semua form untuk Portal Karyawan VIQUAM.

Dipisahkan dari core/forms.py agar tidak mencemari namespace form
yang sudah dipakai portal Pelanggan dan Sopir.
"""

from django import forms
from django.contrib.auth.hashers import make_password
from django.forms import inlineformset_factory

from .models import (
    Feedback, Kendaraan, Pelanggan, Pemesanan, DetailPemesanan,
    Produk, Sopir, StokMasuk,
)

CSS  = 'form-control'
CSS_SELECT = 'form-select'


# ─────────────────────────────────────────────────────────────────────────────
# PRODUK
# ─────────────────────────────────────────────────────────────────────────────

class ProdukForm(forms.ModelForm):
    """
    Form CRUD Produk.
    Field 'stok' di-readonly saat edit — stok hanya boleh bertambah
    via StokMasuk agar audit trail terjaga.
    """

    class Meta:
        model  = Produk
        fields = ['namaProduk', 'ukuranKemasan', 'satuan',
                  'hargaPerDus', 'stok', 'deskripsi', 'foto']
        widgets = {
            'namaProduk':    forms.TextInput(attrs={'class': CSS, 'placeholder': 'Contoh: Air Mineral VIQUAM'}),
            'ukuranKemasan': forms.TextInput(attrs={'class': CSS, 'placeholder': 'Contoh: 600 ml'}),
            'satuan':        forms.Select(attrs={'class': CSS_SELECT}),
            'hargaPerDus':   forms.NumberInput(attrs={'class': CSS, 'min': '0'}),
            'stok':          forms.NumberInput(attrs={'class': CSS, 'min': '0'}),
            'deskripsi':     forms.Textarea(attrs={'class': CSS, 'rows': 3}),
            'foto':          forms.FileInput(attrs={'class': CSS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Mode edit: stok tidak boleh diubah langsung
            self.fields['stok'].widget.attrs['readonly'] = True
            self.fields['stok'].help_text = 'Stok hanya dapat ditambah melalui menu Stok Masuk.'


# ─────────────────────────────────────────────────────────────────────────────
# SOPIR
# ─────────────────────────────────────────────────────────────────────────────

class SopirForm(forms.ModelForm):
    """
    Form CRUD Sopir.
    Password di-hash oleh model.save() — form hanya menerima plain text.
    Saat edit: kosongkan field password di template; abaikan jika kosong,
    update jika diisi (logika ada di SopirUpdateView.form_valid).
    """

    password = forms.CharField(
        label='Password',
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': CSS,
            'placeholder': 'Kosongkan jika tidak ingin mengubah password',
            'autocomplete': 'new-password',
        }),
        help_text='Kosongkan jika tidak ingin mengubah password.',
    )

    class Meta:
        model  = Sopir
        fields = ['nama', 'noHp', 'username', 'password']
        widgets = {
            'nama':     forms.TextInput(attrs={'class': CSS}),
            'noHp':     forms.TextInput(attrs={'class': CSS, 'inputmode': 'numeric'}),
            'username': forms.TextInput(attrs={'class': CSS}),
        }


# ─────────────────────────────────────────────────────────────────────────────
# KENDARAAN
# ─────────────────────────────────────────────────────────────────────────────

class KendaraanForm(forms.ModelForm):
    """
    Form CRUD Kendaraan.
    Dropdown idSopir menampilkan nama sopir secara rapi.
    """

    class Meta:
        model  = Kendaraan
        fields = ['nomorPlat', 'nama', 'jenis', 'idSopir']
        widgets = {
            'nomorPlat': forms.TextInput(attrs={'class': CSS, 'placeholder': 'Contoh: DH 1234 AB'}),
            'nama':      forms.TextInput(attrs={'class': CSS, 'placeholder': 'Contoh: Toyota Avanza'}),
            'jenis':     forms.Select(attrs={'class': CSS_SELECT}),
            'idSopir':   forms.Select(attrs={'class': CSS_SELECT}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tampilkan nama sopir di dropdown, bukan representasi default __str__
        self.fields['idSopir'].queryset = Sopir.objects.order_by('nama')
        self.fields['idSopir'].label_from_instance = lambda obj: f'{obj.nama} ({obj.noHp})'
        self.fields['idSopir'].empty_label = '— Pilih Sopir —'

    def clean_nomorPlat(self):
        """Normalisasi nomor plat: uppercase dan strip whitespace."""
        return self.cleaned_data.get('nomorPlat', '').strip().upper()


# ─────────────────────────────────────────────────────────────────────────────
# PELANGGAN
# ─────────────────────────────────────────────────────────────────────────────

class PelangganCreateForm(forms.ModelForm):
    """
    Form tambah Pelanggan baru.
    Password wajib diisi; model.save() akan meng-hash-nya.
    """

    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': CSS,
            'autocomplete': 'new-password',
        }),
    )
    confirm_password = forms.CharField(
        label='Konfirmasi Password',
        widget=forms.PasswordInput(attrs={
            'class': CSS,
            'autocomplete': 'new-password',
        }),
    )

    class Meta:
        model  = Pelanggan
        fields = ['nama', 'noWa', 'alamat', 'username', 'password',
                  'isLangganan', 'npwp']
        widgets = {
            'nama':        forms.TextInput(attrs={'class': CSS}),
            'noWa':        forms.TextInput(attrs={'class': CSS, 'inputmode': 'numeric'}),
            'alamat':      forms.Textarea(attrs={'class': CSS, 'rows': 2}),
            'username':    forms.TextInput(attrs={'class': CSS}),
            'isLangganan': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'npwp':        forms.TextInput(attrs={'class': CSS, 'placeholder': 'Opsional'}),
        }

    def clean(self):
        cleaned = super().clean()
        pw  = cleaned.get('password')
        cpw = cleaned.get('confirm_password')
        if pw and cpw and pw != cpw:
            raise forms.ValidationError('Password dan konfirmasi password tidak cocok.')
        return cleaned

    def save(self, commit=True):
        # Simpan raw password — model.save() akan meng-hash-nya
        pelanggan = super().save(commit=False)
        pelanggan.password = self.cleaned_data['password']
        if commit:
            pelanggan.save()
        return pelanggan


class PelangganUpdateForm(forms.ModelForm):
    """
    Form edit Pelanggan.
    Password bersifat opsional:
    - Kosong  → password lama dipertahankan (logika di view.form_valid)
    - Diisi   → password baru di-hash dan disimpan
    """

    password = forms.CharField(
        label='Password Baru',
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': CSS,
            'placeholder': 'Kosongkan jika tidak ingin mengubah password',
            'autocomplete': 'new-password',
        }),
        help_text='Kosongkan jika tidak ingin mengubah password.',
    )

    class Meta:
        model  = Pelanggan
        fields = ['nama', 'noWa', 'alamat', 'username', 'password',
                  'isLangganan', 'npwp']
        widgets = {
            'nama':        forms.TextInput(attrs={'class': CSS}),
            'noWa':        forms.TextInput(attrs={'class': CSS, 'inputmode': 'numeric'}),
            'alamat':      forms.Textarea(attrs={'class': CSS, 'rows': 2}),
            'username':    forms.TextInput(attrs={'class': CSS}),
            'isLangganan': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'npwp':        forms.TextInput(attrs={'class': CSS, 'placeholder': 'Opsional'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Kosongkan field password di form — jangan tampilkan hash lama
        self.fields['password'].initial = ''


# ─────────────────────────────────────────────────────────────────────────────
# STOK MASUK
# ─────────────────────────────────────────────────────────────────────────────

class StokMasukForm(forms.ModelForm):
    """
    Form CRUD StokMasuk.
    Jangan ubah stok di sini — model.save() yang menangani update stok
    secara otomatis via F() expression.
    """

    class Meta:
        model  = StokMasuk
        fields = ['idProduk', 'jumlah', 'keterangan']
        widgets = {
            'idProduk':    forms.Select(attrs={'class': CSS_SELECT}),
            'jumlah':      forms.NumberInput(attrs={'class': CSS, 'min': '1'}),
            'keterangan':  forms.Textarea(attrs={'class': CSS, 'rows': 2,
                                                  'placeholder': 'Keterangan (opsional)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['idProduk'].queryset = Produk.objects.order_by('namaProduk')
        self.fields['idProduk'].label_from_instance = (
            lambda obj: f'{obj.namaProduk} ({obj.ukuranKemasan}) — Stok: {obj.stok}'
        )
        self.fields['idProduk'].empty_label = '— Pilih Produk —'


# ─────────────────────────────────────────────────────────────────────────────
# PEMESANAN + DETAIL (inlineformset)
# ─────────────────────────────────────────────────────────────────────────────

class PemesananForm(forms.ModelForm):
    """
    Form header Pemesanan.
    Field 'total' readonly — dihitung otomatis oleh model via update_total().
    Field 'updated_by', 'last_updated', 'keterangan_admin' diisi di view.
    """

    class Meta:
        model  = Pemesanan
        fields = [
            'idPelanggan', 'tanggalPemesanan', 'alamatPengiriman',
            'idSopir', 'status',
            'jenisPembayaran', 'statusPembayaran',
            'nominalDibayar', 'sisaTagihan', 'jatuhTempo',
            'buktiBayar', 'fotoPengiriman', 'total',
        ]
        widgets = {
            'idPelanggan':      forms.Select(attrs={'class': CSS_SELECT}),
            'tanggalPemesanan': forms.DateTimeInput(
                attrs={'class': CSS, 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'alamatPengiriman': forms.Textarea(attrs={'class': CSS, 'rows': 2}),
            'idSopir':          forms.Select(attrs={'class': CSS_SELECT}),
            'status':           forms.Select(attrs={'class': CSS_SELECT}),
            'jenisPembayaran':  forms.Select(attrs={'class': CSS_SELECT}),
            'statusPembayaran': forms.Select(attrs={'class': CSS_SELECT}),
            'nominalDibayar':   forms.NumberInput(attrs={'class': CSS, 'min': '0'}),
            'sisaTagihan':      forms.NumberInput(attrs={
                'class': CSS, 'readonly': True,
            }),
            'jatuhTempo':       forms.DateInput(
                attrs={'class': CSS, 'type': 'date'},
                format='%Y-%m-%d',
            ),
            'buktiBayar':       forms.FileInput(attrs={'class': CSS}),
            'fotoPengiriman':   forms.FileInput(attrs={'class': CSS}),
            # total: readonly — dihitung model
            'total':            forms.NumberInput(attrs={
                'class': CSS, 'readonly': True,
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['idPelanggan'].queryset = Pelanggan.objects.order_by('nama')
        self.fields['idPelanggan'].label_from_instance = (
            lambda obj: f'{obj.nama} ({obj.noWa})'
        )
        self.fields['idPelanggan'].empty_label = '— Pilih Pelanggan —'

        self.fields['idSopir'].queryset = Sopir.objects.order_by('nama')
        self.fields['idSopir'].label_from_instance = lambda obj: obj.nama
        self.fields['idSopir'].empty_label = '— Pilih Sopir (opsional) —'
        self.fields['idSopir'].required = False

        # total tidak boleh diedit manual
        self.fields['total'].required = False
        self.fields['total'].label = 'Total Harga (otomatis)'

        # Format datetime-local membutuhkan initial yang tepat
        if self.instance and self.instance.pk and self.instance.tanggalPemesanan:
            self.initial['tanggalPemesanan'] = (
                self.instance.tanggalPemesanan.strftime('%Y-%m-%dT%H:%M')
            )


class DetailPemesananForm(forms.ModelForm):
    """
    Form satu baris detail pesanan (dipakai dalam inlineformset).
    subTotal dihitung otomatis oleh model.save().
    """

    class Meta:
        model  = DetailPemesanan
        fields = ['idProduk', 'jumlah']
        widgets = {
            'idProduk': forms.Select(attrs={'class': CSS_SELECT + ' produk-select'}),
            'jumlah':   forms.NumberInput(attrs={
                'class': CSS + ' jumlah-input', 'min': '1',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['idProduk'].queryset = Produk.objects.filter(stok__gt=0).order_by('namaProduk')
        self.fields['idProduk'].label_from_instance = (
            lambda obj: f'{obj.namaProduk} ({obj.ukuranKemasan}) — Stok: {obj.stok}'
        )
        self.fields['idProduk'].empty_label = '— Pilih Produk —'


# Inlineformset: satu Pemesanan → banyak DetailPemesanan
# extra=1  : satu baris kosong saat create
# can_delete=True : karyawan bisa hapus baris detail
DetailPemesananFormSet = inlineformset_factory(
    Pemesanan,
    DetailPemesanan,
    form=DetailPemesananForm,
    extra=1,
    can_delete=True,
    min_num=1,          # minimal 1 produk per pesanan
    validate_min=True,
)
