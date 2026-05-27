from django.urls import path, include
from . import views, karyawan_views, pimpinan_views
from .views import (
    StaffUserListView,
    StaffUserCreateView,
    StaffUserUpdateView,
    StaffUserDeleteView,
    StaffUserPasswordResetView,
)

urlpatterns = [

    # ── Laporan PDF ───────────────────────────────────────────────────────────
    # ── Laporan Sistem (Karyawan & Pimpinan) ──────────────────────────────────
    path('laporan/pelanggan/',           karyawan_views.laporan_pelanggan,           name='laporan-pelanggan'),
    path('laporan/produk/',              karyawan_views.laporan_produk,              name='laporan-produk'),
    path('laporan/sopir-kendaraan/',     karyawan_views.laporan_sopir_kendaraan,     name='laporan-sopir-kendaraan'),
    path('laporan/pemesanan-pendapatan/', karyawan_views.laporan_pemesanan_pendapatan, name='laporan-pemesanan-pendapatan'),
    path('laporan/feedback/',            karyawan_views.laporan_feedback,            name='laporan-feedback'),


    # ── Sopir (portal sopir) ──────────────────────────────────────────────────
    path('sopir/login/',                    views.sopir_login,           name='sopir-login'),
    path('sopir/logout/',                   views.sopir_logout,          name='sopir-logout'),
    path('sopir/dashboard/',               views.sopir_dashboard,        name='sopir-dashboard'),
    path('sopir/edit-pengiriman/<int:pk>/', views.sopir_edit_pengiriman, name='sopir-edit-pengiriman'),
    path('sopir/account/',                  views.sopir_account,         name='sopir-account'),

    # ── Pelanggan (portal pelanggan) ──────────────────────────────────────────
    path('',                              views.landing_page,          name='landing'),
    path('register/',                     views.pelanggan_register,    name='pelanggan_register'),
    path('login/',                        views.pelanggan_login,       name='pelanggan_login'),
    path('logout/',                       views.pelanggan_logout,      name='pelanggan_logout'),
    path('home/',                         views.pelanggan_home,        name='pelanggan_home'),
    path('produk/',                       views.list_produk,           name='list_produk'),
    path('produk/<int:pk>/detail/',       views.detail_produk,         name='detail_produk'),
    path('keranjang/',                    views.view_keranjang,        name='view_keranjang'),
    path('keranjang/add/<int:pk>/',       views.tambah_ke_keranjang,   name='tambah_ke_keranjang'),
    path('keranjang/update/<int:pk>/',    views.update_keranjang,      name='update_keranjang'),
    path('keranjang/remove/<int:pk>/',    views.remove_from_keranjang, name='remove_from_keranjang'),
    path('checkout/',                     views.checkout_pemesanan,    name='checkout_pemesanan'),
    path('riwayat/',                      views.riwayat_pesanan,       name='riwayat_pesanan'),
    path('riwayat/<int:pk>/detail/',      views.detail_pesanan,        name='detail_pesanan'),
    path('riwayat/<int:pk>/batal/',       views.batal_pesanan,         name='batal_pesanan'),
    path('akun/',                         views.pelanggan_account,     name='pelanggan_account'),
    path('akun/kirim-feedback/',          views.kirim_feedback,        name='kirim_feedback'),

    # ── Portal Pimpinan — Auth & Read-Only ───────────────────────────────────
    path('pimpinan/login/',    views.pimpinan_login,    name='pimpinan_login'),
    path('pimpinan/logout/',   views.pimpinan_logout,   name='pimpinan_logout'),
    path('pimpinan/dashboard/', views.pimpinan_dashboard, name='pimpinan_dashboard'),
    path('pimpinan/produk/',   views.pimpinan_produk_list,   name='pimpinan_produk'),
    path('pimpinan/pemesanan/', views.pimpinan_pemesanan_list, name='pimpinan_pemesanan'),
    path('pimpinan/pemesanan/<int:id>/detail/', views.pimpinan_pemesanan_detail_ajax, name='pimpinan_pemesanan_detail_ajax'),
    path('pimpinan/pelanggan/', views.pimpinan_pelanggan_list, name='pimpinan_pelanggan'),
    path('pimpinan/sopir/',    views.pimpinan_sopir_list,    name='pimpinan_sopir'),

    # ── Portal Pimpinan — Staff User Management (lama, tetap dipertahankan) ──
    path('pimpinan/users/',                         StaffUserListView.as_view(),         name='pimpinan_user_list'),
    path('pimpinan/users/tambah/',                  StaffUserCreateView.as_view(),        name='pimpinan_user_create'),
    path('pimpinan/users/<int:pk>/edit/',            StaffUserUpdateView.as_view(),        name='pimpinan_user_update'),
    path('pimpinan/users/<int:pk>/hapus/',           StaffUserDeleteView.as_view(),        name='pimpinan_user_delete'),
    path('pimpinan/users/<int:pk>/reset-password/',  StaffUserPasswordResetView.as_view(), name='pimpinan_user_password_reset'),

    # ── Portal Pimpinan — Manajemen Akun Karyawan (baru) ─────────────────────
    path('pimpinan/karyawan/',                          pimpinan_views.KaryawanAccountListView.as_view(),   name='pimpinan_karyawan_list'),
    path('pimpinan/karyawan/tambah/',                   pimpinan_views.KaryawanAccountCreateView.as_view(), name='pimpinan_karyawan_create'),
    path('pimpinan/karyawan/<int:pk>/edit/',             pimpinan_views.KaryawanAccountUpdateView.as_view(), name='pimpinan_karyawan_update'),
    path('pimpinan/karyawan/<int:pk>/hapus/',            pimpinan_views.KaryawanAccountDeleteView.as_view(), name='pimpinan_karyawan_delete'),
    path('pimpinan/karyawan/<int:pk>/reset-password/',   pimpinan_views.KaryawanPasswordResetView.as_view(), name='pimpinan_karyawan_password_reset'),

    # ── Portal Karyawan — Auth ────────────────────────────────────────────────
    path('karyawan/login/',    karyawan_views.karyawan_login,  name='karyawan_login'),
    path('karyawan/logout/',   karyawan_views.karyawan_logout, name='karyawan_logout'),
    path('karyawan/dashboard/', karyawan_views.KaryawanDashboardView.as_view(), name='karyawan_dashboard'),

    # ── Portal Karyawan — Produk ──────────────────────────────────────────────
    path('karyawan/produk/',                karyawan_views.ProdukListView.as_view(),   name='karyawan_produk_list'),
    path('karyawan/produk/tambah/',         karyawan_views.ProdukCreateView.as_view(), name='karyawan_produk_create'),
    path('karyawan/produk/<int:pk>/edit/',  karyawan_views.ProdukUpdateView.as_view(), name='karyawan_produk_update'),
    path('karyawan/produk/<int:pk>/hapus/', karyawan_views.ProdukDeleteView.as_view(), name='karyawan_produk_delete'),

    # ── Portal Karyawan — Sopir ───────────────────────────────────────────────
    path('karyawan/sopir/',                karyawan_views.SopirListView.as_view(),   name='karyawan_sopir_list'),
    path('karyawan/sopir/tambah/',         karyawan_views.SopirCreateView.as_view(), name='karyawan_sopir_create'),
    path('karyawan/sopir/<int:pk>/edit/',  karyawan_views.SopirUpdateView.as_view(), name='karyawan_sopir_update'),
    path('karyawan/sopir/<int:pk>/hapus/', karyawan_views.SopirDeleteView.as_view(), name='karyawan_sopir_delete'),

    # ── Portal Karyawan — Kendaraan ───────────────────────────────────────────
    path('karyawan/kendaraan/',                    karyawan_views.KendaraanListView.as_view(),   name='karyawan_kendaraan_list'),
    path('karyawan/kendaraan/tambah/',             karyawan_views.KendaraanCreateView.as_view(), name='karyawan_kendaraan_create'),
    path('karyawan/kendaraan/<str:pk>/edit/',      karyawan_views.KendaraanUpdateView.as_view(), name='karyawan_kendaraan_update'),
    path('karyawan/kendaraan/<str:pk>/hapus/',     karyawan_views.KendaraanDeleteView.as_view(), name='karyawan_kendaraan_delete'),

    # ── Portal Karyawan — Pelanggan ───────────────────────────────────────────
    path('karyawan/pelanggan/',                karyawan_views.PelangganListView.as_view(),   name='karyawan_pelanggan_list'),
    path('karyawan/pelanggan/tambah/',         karyawan_views.PelangganCreateView.as_view(), name='karyawan_pelanggan_create'),
    path('karyawan/pelanggan/<int:pk>/edit/',  karyawan_views.PelangganUpdateView.as_view(), name='karyawan_pelanggan_update'),
    path('karyawan/pelanggan/<int:pk>/hapus/', karyawan_views.PelangganDeleteView.as_view(), name='karyawan_pelanggan_delete'),

    # ── Portal Karyawan — Stok Masuk ─────────────────────────────────────────
    path('karyawan/stok/',                karyawan_views.StokMasukListView.as_view(),   name='karyawan_stok_list'),
    path('karyawan/stok/tambah/',         karyawan_views.StokMasukCreateView.as_view(), name='karyawan_stok_create'),
    path('karyawan/stok/<int:pk>/edit/',  karyawan_views.StokMasukUpdateView.as_view(), name='karyawan_stok_update'),
    path('karyawan/stok/<int:pk>/hapus/', karyawan_views.StokMasukDeleteView.as_view(), name='karyawan_stok_delete'),

    # ── Portal Karyawan — Pemesanan ───────────────────────────────────────────
    path('karyawan/pemesanan/',                karyawan_views.PemesananListView.as_view(),   name='karyawan_pemesanan_list'),
    path('karyawan/pemesanan/tambah/',         karyawan_views.PemesananCreateView.as_view(), name='karyawan_pemesanan_create'),
    path('karyawan/pemesanan/<int:pk>/edit/',  karyawan_views.PemesananUpdateView.as_view(), name='karyawan_pemesanan_update'),
    path('karyawan/pemesanan/<int:pk>/hapus/', karyawan_views.PemesananDeleteView.as_view(), name='karyawan_pemesanan_delete'),

    # ── Portal Karyawan — Feedback ────────────────────────────────────────────
    path('karyawan/feedback/',                karyawan_views.FeedbackListView.as_view(),   name='karyawan_feedback_list'),
    path('karyawan/feedback/<int:pk>/',       karyawan_views.FeedbackDetailView.as_view(), name='karyawan_feedback_detail'),
    path('karyawan/feedback/<int:pk>/hapus/', karyawan_views.FeedbackDeleteView.as_view(), name='karyawan_feedback_delete'),
]
