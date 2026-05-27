from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(self.create_groups_and_permissions, sender=self)

    def create_groups_and_permissions(self, sender, **kwargs):
        """
        Buat Group 'Pimpinan' dan 'Karyawan' beserta permission-nya
        secara otomatis setelah setiap migrate.

        Idempotent: aman dijalankan berulang kali — get_or_create
        tidak akan duplikasi data.
        """
        from django.contrib.auth.models import Group, Permission
        from django.contrib.contenttypes.models import ContentType
        from .models import (
            Pelanggan, Produk, StokMasuk, Pemesanan,
            DetailPemesanan, Feedback, Sopir, Kendaraan,
        )

        # ── Group: Pimpinan ───────────────────────────────────────────────────
        # Pimpinan tidak perlu permission Django — aksesnya dikontrol
        # sepenuhnya oleh PimpinanRequiredMixin di portal custom.
        Group.objects.get_or_create(name='Pimpinan')

        # ── Group: Karyawan ───────────────────────────────────────────────────
        # Karyawan mendapat akses CRUD penuh ke semua model operasional.
        # Permission ini dipakai sebagai referensi; enforcement utama
        # dilakukan di KaryawanRequiredMixin (cek Group, bukan permission object).
        karyawan_group, karyawan_created = Group.objects.get_or_create(name='Karyawan')

        if karyawan_created:
            operasional_models = [
                Pelanggan, Produk, StokMasuk, Pemesanan,
                DetailPemesanan, Feedback, Sopir, Kendaraan,
            ]
            perms_to_add = []
            for model in operasional_models:
                ct = ContentType.objects.get_for_model(model)
                perms_to_add.extend(Permission.objects.filter(content_type=ct))

            karyawan_group.permissions.add(*perms_to_add)
