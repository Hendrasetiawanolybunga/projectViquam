"""
core/mixins.py
==============
Mixin keamanan terpusat untuk dua portal custom VIQUAM.

Hierarki akses:
  Superuser  → bisa masuk ke mana saja (Django admin)
  Pimpinan   → hanya portal /pimpinan/  (PimpinanRequiredMixin)
  Karyawan   → hanya portal /karyawan/  (KaryawanRequiredMixin)

Aturan isolasi KETAT:
  - Pimpinan TIDAK BOLEH mengakses view yang memakai KaryawanRequiredMixin.
  - Karyawan TIDAK BOLEH mengakses view yang memakai PimpinanRequiredMixin.
  - Kedua mixin redirect ke halaman login masing-masing, bukan raise 403,
    agar tidak membocorkan keberadaan URL ke pihak yang tidak berhak.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect


# ─────────────────────────────────────────────────────────────────────────────
# Helper: cek keanggotaan group (satu query, di-cache per request oleh Django)
# ─────────────────────────────────────────────────────────────────────────────

def _is_pimpinan(user):
    """Return True jika user tergabung dalam Group 'Pimpinan'."""
    return user.groups.filter(name='Pimpinan').exists()


def _is_karyawan(user):
    """
    Return True jika user tergabung dalam Group 'Karyawan'.

    Superuser sengaja TIDAK dianggap Karyawan — superuser menggunakan
    Django admin, bukan portal karyawan.
    """
    return (
        not user.is_superuser
        and user.is_staff
        and user.groups.filter(name='Karyawan').exists()
    )


# ─────────────────────────────────────────────────────────────────────────────
# KaryawanRequiredMixin
# ─────────────────────────────────────────────────────────────────────────────

class KaryawanRequiredMixin(LoginRequiredMixin):
    """
    Mixin untuk semua CBV di portal Karyawan (/karyawan/).

    Lapis keamanan:
    1. LoginRequiredMixin  — user harus terautentikasi.
    2. dispatch() override — user harus tergabung dalam Group 'Karyawan'.
    3. Pimpinan secara eksplisit DITOLAK meski is_staff=True,
       karena Pimpinan bukan Karyawan operasional.

    Redirect target: 'karyawan_login'
    """

    login_url = 'karyawan_login'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Silakan login terlebih dahulu.')
            return redirect('karyawan_login')

        # SECURITY: Pimpinan tidak boleh masuk portal Karyawan.
        # Cek ini harus sebelum cek _is_karyawan agar tidak ada celah
        # jika seseorang tergabung di dua group sekaligus.
        if _is_pimpinan(request.user):
            messages.error(
                request,
                'Akses ditolak. Portal Karyawan tidak dapat diakses oleh Pimpinan.'
            )
            return redirect('pimpinan_dashboard')

        # Cek keanggotaan Group Karyawan
        if not _is_karyawan(request.user):
            messages.error(
                request,
                'Akses ditolak. Anda tidak memiliki hak akses ke portal ini.'
            )
            return redirect('karyawan_login')

        return super().dispatch(request, *args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# PimpinanRequiredMixin
# ─────────────────────────────────────────────────────────────────────────────

class PimpinanRequiredMixin(LoginRequiredMixin):
    """
    Mixin untuk semua CBV di portal Pimpinan (/pimpinan/).

    Lapis keamanan:
    1. LoginRequiredMixin  — user harus terautentikasi.
    2. dispatch() override — user harus tergabung dalam Group 'Pimpinan'.
    3. Karyawan secara eksplisit DITOLAK meski is_staff=True.

    Redirect target: 'pimpinan_login'
    """

    login_url = 'pimpinan_login'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Silakan login terlebih dahulu.')
            return redirect('pimpinan_login')

        # SECURITY: Karyawan tidak boleh masuk portal Pimpinan.
        if _is_karyawan(request.user):
            messages.error(
                request,
                'Akses ditolak. Portal Pimpinan tidak dapat diakses oleh Karyawan.'
            )
            return redirect('karyawan_dashboard')

        # Cek keanggotaan Group Pimpinan
        if not _is_pimpinan(request.user):
            messages.error(
                request,
                'Akses ditolak. Halaman ini hanya untuk Pimpinan.'
            )
            return redirect('pimpinan_login')

        return super().dispatch(request, *args, **kwargs)
