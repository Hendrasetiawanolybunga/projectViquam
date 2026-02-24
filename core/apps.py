from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Import inside the method to avoid AppRegistryNotReady exception
        from django.db.models.signals import post_migrate
        from django.contrib.auth.models import Group, Permission
        from django.contrib.contenttypes.models import ContentType
        from .models import Pelanggan, Produk, StokMasuk, Pemesanan, DetailPemesanan, Feedback
        
        # Connect the signal
        post_migrate.connect(self.create_groups_and_permissions, sender=self)
    
    def create_groups_and_permissions(self, sender, **kwargs):
        """
        Automatically create Pimpinan and Karyawan groups with specific permissions
        after migrations
        """
        from django.contrib.auth.models import Group, Permission
        from django.contrib.contenttypes.models import ContentType
        from .models import Pelanggan, Produk, StokMasuk, Pemesanan, DetailPemesanan, Feedback
        
        # Create or get the Pimpinan group
        pimpinan_group, pimpinan_created = Group.objects.get_or_create(name='Pimpinan')
        
        # Karyawan group removed - delivery verification now handled by Sopir only
        
        # Permissions for Pimpinan: View-only for Feedback
        if pimpinan_created:
            feedback_ct = ContentType.objects.get_for_model(Feedback)
            
            # Pimpinan permissions: View-only for Feedback
            pimpinan_permissions = Permission.objects.filter(
                content_type=feedback_ct,
                codename__in=['view_feedback']
            )
            
            # Add permissions to Pimpinan group
            pimpinan_group.permissions.add(*pimpinan_permissions)