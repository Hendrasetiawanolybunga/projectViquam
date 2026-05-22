from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.urls import path, reverse
from django.utils.html import format_html
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
import locale
from decimal import Decimal
from django.contrib.humanize.templatetags.humanize import intcomma

from .models import Pelanggan, Sopir, Kendaraan, Produk, StokMasuk, Pemesanan, DetailPemesanan, Feedback
from . import views

class CustomAdminSite(admin.AdminSite):
    site_header = 'Viquam Administration'
    site_title = 'Viquam Admin'
    index_title = 'Dashboard'
    index_template = 'core/dashboard.html'
    
    def index(self, request, extra_context=None):
        """
        Override the default admin index view to use our custom dashboard
        """
       
        from . import views
        
       
        dashboard_context = views.get_dashboard_context()
        
       
        if extra_context is None:
            extra_context = {}
        extra_context.update(dashboard_context)
        
       
        extra_context['user'] = request.user
        
      
        if not request.user.is_superuser and request.user.groups.filter(name='Pimpinan').exists():
            extra_context['is_pimpinan'] = True
        else:
            extra_context['is_pimpinan'] = False
        
        return super().index(request, extra_context)
    
    def get_app_list(self, request):
        """
        Override to customize app list based on user group
        """
       
        if not request.user.is_superuser and request.user.groups.filter(name='Pimpinan').exists():
          
            app_list = super().get_app_list(request)
            
          
            allowed_models = ['Feedback']
            
          
            filtered_app_list = []
            for app in app_list:
                filtered_models = []
                for model in app.get('models', []):
                   
                    if model.get('object_name') in allowed_models:
                       
                        filtered_models.append(model)
                
              
                if filtered_models:
                    app['models'] = filtered_models
                    filtered_app_list.append(app)
            
            return filtered_app_list
        
      
        return super().get_app_list(request)

custom_admin_site = CustomAdminSite(name='custom_admin')

try:
    locale.setlocale(locale.LC_ALL, 'id_ID.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'id_ID')
    except locale.Error:
        pass

def currency_format(amount):
    if amount is None:
        return 'Rp 0'
    amount = int(amount)
    return format_html('Rp {}', intcomma(amount))
currency_format.short_description = 'Harga'

class ActionColumnMixin:
    def actions_column(self, obj):
        change_url = reverse(f'admin:{obj._meta.app_label}_{obj._meta.model_name}_change', args=[obj.pk])
        delete_url = reverse(f'admin:{obj._meta.app_label}_{obj._meta.model_name}_delete', args=[obj.pk])
        
        return format_html(
            f'<a href="{change_url}" title="Ubah" style="color: green;"><i class="fas fa-edit"></i></a>&nbsp;&nbsp;'
            f'<a href="{delete_url}" title="Hapus" style="color: red;"><i class="fas fa-trash"></i></a>'
        )
    actions_column.short_description = 'Aksi' 
    actions_column.allow_tags = True
    

# Custom User Admin to handle plain text password storage
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User


class UserAdmin(BaseUserAdmin):
    def save_model(self, request, obj, form, change):
        # Check if password is being set/changed
        password = form.cleaned_data.get('password')
        
        # If the password doesn't already start with our plain_text prefix,
        # we need to hash it using our custom hasher
        if password and not password.startswith('plain_text$'):
            # Use set_password to trigger our custom hasher
            obj.set_password(password)
        elif password and password.startswith('plain_text$'):
            # If it already has the prefix, we can save it directly
            # but we still need to ensure it's properly formatted
            obj.password = password
        
        super().save_model(request, obj, form, change)


# Register built-in Django models with custom admin site
admin.site.unregister(User)
admin.site.unregister(Group)

custom_admin_site.register(User, UserAdmin)
# Note: Group management is intentionally unregistered to hide it from the sidebar

@admin.register(Pelanggan, site=custom_admin_site)
class PelangganAdmin(ActionColumnMixin, admin.ModelAdmin):
    list_display = ('nama', 'noWa', 'username', 'isLangganan_display', 'npwp_display', 'actions_column')
    search_fields = ('nama', 'username', 'noWa', 'npwp')
    list_filter = ('isLangganan',)
    
    def isLangganan_display(self, obj):
        """Display customer type with icon"""
        if obj.isLangganan:
            return '✓ Langganan'
        return '✗ Umum'
    isLangganan_display.short_description = 'Tipe Pelanggan'
    
    def npwp_display(self, obj):
        """Display NPWP if available"""
        return obj.npwp if obj.npwp else '-'
    npwp_display.short_description = 'NPWP'

@admin.register(Sopir, site=custom_admin_site)
class SopirAdmin(ActionColumnMixin, admin.ModelAdmin):
    list_display = ('nama', 'noHp', 'username', 'actions_column')
    search_fields = ('nama', 'username', 'noHp')



@admin.register(Kendaraan, site=custom_admin_site)
class KendaraanAdmin(ActionColumnMixin, admin.ModelAdmin):
    list_display = ('nomorPlat', 'nama', 'jenis', 'idSopir', 'actions_column')
    list_filter = ('jenis',)
    search_fields = ('nomorPlat', 'nama')
    autocomplete_fields = ['idSopir']


@admin.register(Produk, site=custom_admin_site)
class ProdukAdmin(ActionColumnMixin, admin.ModelAdmin):
    # Mengubah list_display agar hargaPerDus (field asli) muncul, 
    # sehingga list_editable dapat berfungsi.
    list_display = ('namaProduk', 'ukuranKemasan', 'hargaPerDus', 'stok', 'actions_column') 
    search_fields = ('namaProduk', 'ukuranKemasan')
    list_editable = ('hargaPerDus',) 
    readonly_fields = () 


@admin.register(StokMasuk, site=custom_admin_site)
class StokMasukAdmin(ActionColumnMixin, admin.ModelAdmin):
    list_display = ('idProduk', 'jumlah', 'tanggal', 'keterangan', 'actions_column')
    list_filter = ('tanggal', 'idProduk')
    date_hierarchy = 'tanggal'
    autocomplete_fields = ['idProduk']


# Provinsi, Kabupaten, Kecamatan, Kelurahan models have been removed
# Location data is now handled via latitude/longitude coordinates


class DetailPemesananInline(admin.TabularInline):
    def sub_total_formatted(self, obj):
        return currency_format(obj.subTotal)
    sub_total_formatted.short_description = 'Sub Total'

    model = DetailPemesanan
    fields = ('idProduk', 'jumlah', 'subTotal') 
    readonly_fields = ('subTotal',)
    extra = 1 
    autocomplete_fields = ['idProduk']
    
    verbose_name = 'Detail Produk'
    verbose_name_plural = 'Detail Produk'





@admin.register(Pemesanan, site=custom_admin_site)
class PemesananAdmin(ActionColumnMixin, admin.ModelAdmin):
    def total_formatted(self, obj):
        return currency_format(obj.total)
    total_formatted.short_description = 'Total Harga'
    
    def nominalDibayar_formatted(self, obj):
        return currency_format(obj.nominalDibayar)
    nominalDibayar_formatted.short_description = 'Nominal Dibayar'
    
    def sisaTagihan_formatted(self, obj):
        return currency_format(obj.sisaTagihan)
    sisaTagihan_formatted.short_description = 'Sisa Tagihan'

    list_display = ('idPelanggan', 'tanggalPemesanan', 'total_formatted', 'jenisPembayaran', 'statusPembayaran', 'nominalDibayar_formatted', 'sisaTagihan_formatted', 'status', 'idSopir', 'actions_column')
    list_filter = ('status', 'jenisPembayaran', 'statusPembayaran')
    search_fields = ('idPelanggan__nama', 'idPemesanan__startswith')
    date_hierarchy = 'tanggalPemesanan'
    
    readonly_fields = ('total', 'updated_by', 'last_updated', 'sisaTagihan') 
    
    fieldsets = (
        ('Informasi Dasar Pemesanan', {
            'fields': ('idPelanggan', 'latitude', 'longitude', 'alamatPengiriman', 'status', 'idSopir', 'total', 'tanggalPemesanan')
        }),
        ('Informasi Pembayaran', {
            'fields': ('jenisPembayaran', 'statusPembayaran', 'nominalDibayar', 'sisaTagihan', 'jatuhTempo'),
        }),
        ('Bukti Transaksi (Opsional)', {
            'fields': ('buktiBayar', 'fotoPengiriman'),
            'classes': ('collapse',),
        }),
        ('Audit Admin (Log Perubahan)', {
            'fields': ('updated_by', 'last_updated', 'keterangan_admin'),
            'classes': ('collapse',),
        }),
    )

    inlines = [DetailPemesananInline]

    autocomplete_fields = ['idPelanggan', 'idSopir']
    
    def save_model(self, request, obj, form, change):
        """
        Override save_model to automatically track admin activities and update payment status
        """
       
        obj.updated_by = request.user
        
        # Auto-update status pembayaran based on nominal dibayar
        obj.update_status_pembayaran()
    
        if change:
            
            # Track payment-related changes
            if 'nominalDibayar' in form.changed_data or 'statusPembayaran' in form.changed_data:
                obj.keterangan_admin = f"{request.user.username} memperbarui pembayaran: {obj.statusPembayaran} (Dibayar: {obj.nominalDibayar}, Sisa: {obj.sisaTagihan})"
            elif 'status' in form.changed_data:
                obj.keterangan_admin = f"{request.user.username} mengubah status menjadi {obj.status}"
            elif 'idSopir' in form.changed_data:
                sopir_nama = obj.idSopir.nama if obj.idSopir else 'Tidak ada'
                obj.keterangan_admin = f"{request.user.username} menugaskan sopir: {sopir_nama}"
            else:
                obj.keterangan_admin = f"{request.user.username} memperbarui data pesanan"
        else:
        
            obj.keterangan_admin = f"{request.user.username} membuat pesanan baru via Admin"
        
        super().save_model(request, obj, form, change) 

    def get_urls(self):
        urls = super().get_urls()

       
        def has_report_permission(request):
          
            return (
                request.user.is_superuser or 
                request.user.groups.filter(name='Pimpinan').exists()
            )

    
        def protected_view(view_func):
            def wrapper(request, *args, **kwargs):
                if not has_report_permission(request):
                 
                    from django.contrib import messages
                    messages.error(request, 'Anda tidak memiliki izin untuk mengakses laporan ini.')
                    from django.shortcuts import redirect
                    return redirect('admin:index')
                return view_func(request, *args, **kwargs)
            return wrapper

        report_urls = [
          
            path('laporan/pemesanan-pendapatan/', self.admin_site.admin_view(protected_view(views.admin_laporan_pemesanan_pendapatan)), name='core_pemesanan_laporan'),
          
            path('laporan/pelanggan/', self.admin_site.admin_view(protected_view(views.admin_laporan_pelanggan)), name='laporan-pelanggan'),
            path('laporan/produk/', self.admin_site.admin_view(protected_view(views.admin_laporan_produk)), name='laporan-produk'),
            path('laporan/sopir-kendaraan/', self.admin_site.admin_view(protected_view(views.admin_laporan_sopir_kendaraan)), name='laporan-sopir-kendaraan'),
            path('laporan/feedback/', self.admin_site.admin_view(protected_view(views.admin_laporan_feedback)), name='laporan-feedback'),
            # PDF Laporan
            path('laporan/pelanggan/pdf/', self.admin_site.admin_view(protected_view(views.laporan_pelanggan)), name='laporan-pelanggan-pdf'),
            path('laporan/produk/pdf/', self.admin_site.admin_view(protected_view(views.laporan_produk)), name='laporan-produk-pdf'),
            path('laporan/sopir-kendaraan/pdf/', self.admin_site.admin_view(protected_view(views.laporan_sopir_kendaraan)), name='laporan-sopir-kendaraan-pdf'),
            path('laporan/pemesanan-pendapatan/pdf/', self.admin_site.admin_view(protected_view(views.laporan_pemesanan_pendapatan)), name='laporan-pemesanan-pendapatan-pdf'),
            path('laporan/feedback/pdf/', self.admin_site.admin_view(protected_view(views.laporan_feedback)), name='laporan-feedback-pdf'),
        ]

        return report_urls + urls

    def response_change(self, request, obj):
       
        if obj.status == 'Dibatalkan':
         
            from .models import DetailPemesanan, Produk
            original_obj = self.model.objects.get(pk=obj.pk)
            
         
            if original_obj.status != 'Dibatalkan':
             
                for detail in obj.detailpemesanan_set.all():
                  
                    product = detail.idProduk
                    product.stok += detail.jumlah
                    product.save()
        
        return super().response_change(request, obj)

@admin.register(Feedback, site=custom_admin_site)
class FeedbackAdmin(ActionColumnMixin, admin.ModelAdmin):
    list_display = ('idPelanggan', 'tanggal', 'isi_preview', 'actions_column')
    search_fields = ('idPelanggan__nama', 'isi')
    list_filter = ('tanggal',)
    date_hierarchy = 'tanggal'
    readonly_fields = ('tanggal',)
    autocomplete_fields = ['idPelanggan']
    
    def isi_preview(self, obj):
        return f'{obj.isi[:50]}...' if len(obj.isi) > 50 else obj.isi
    isi_preview.short_description = 'Isi Feedback (Ringkasan)'