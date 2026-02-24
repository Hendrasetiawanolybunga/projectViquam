from django.core.management.base import BaseCommand
from django.db import connection
from core.models import Provinsi, Kabupaten, Kecamatan, Kelurahan

class Command(BaseCommand):
    help = 'Seed wilayah data for NTT'

    def handle(self, *args, **options):
        # Create Provinsi
        provinsi, created = Provinsi.objects.get_or_create(
            nama="Nusa Tenggara Timur",
            defaults={'nama': "Nusa Tenggara Timur"}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created Provinsi: {provinsi.nama}'))
        else:
            self.stdout.write(self.style.WARNING(f'Provinsi already exists: {provinsi.nama}'))

        # Create Kabupaten
        kabupaten_data = [
            {"nama": "Kota Kupang"},
            {"nama": "Kab. Sabu Raijua"},
            {"nama": "Kab. Timor Tengah Utara"}
        ]

        kabupaten_objects = []
        for kab_data in kabupaten_data:
            # Try different approaches to handle the schema inconsistency
            try:
                # Attempt to create with the model field name
                kabupaten, created = Kabupaten.objects.get_or_create(
                    idProvinsi=provinsi,
                    nama=kab_data["nama"],
                    defaults={'nama': kab_data["nama"]}
                )
            except:
                # If that fails, try using raw SQL to handle the database column directly
                with connection.cursor() as cursor:
                    # Check if the kabupaten already exists
                    cursor.execute(
                        "SELECT idKabupaten FROM core_kabupaten WHERE nama = %s AND provinsi_id = %s",
                        [kab_data["nama"], provinsi.idProvinsi]
                    )
                    row = cursor.fetchone()
                    if row:
                        # Kabupaten already exists
                        kabupaten = Kabupaten.objects.get(idKabupaten=row[0])
                        created = False
                    else:
                        # Create new kabupaten
                        cursor.execute(
                            "INSERT INTO core_kabupaten (nama, provinsi_id) VALUES (%s, %s)",
                            [kab_data["nama"], provinsi.idProvinsi]
                        )
                        # Get the ID of the newly inserted record
                        kabupaten_id = cursor.lastrowid
                        kabupaten = Kabupaten.objects.get(idKabupaten=kabupaten_id)
                        created = True
            
            kabupaten_objects.append(kabupaten)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created Kabupaten: {kabupaten.nama}'))
            else:
                self.stdout.write(self.style.WARNING(f'Kabupaten already exists: {kabupaten.nama}'))

        # Create Kecamatan and Kelurahan for each Kabupaten
        kecamatan_kelurahan_data = {
            "Kota Kupang": [
                {"namaKecamatan": "Oebobo", "kelurahans": ["Oesapa", "Oebufu", "Naioni", "Oesapa Barat", "Oetete"]},
                {"namaKecamatan": "Kelapa Lima", "kelurahans": ["Airnona", "Fatufeto", "Penfui", "Liliba", "Nunbaun Delha"]},
                {"namaKecamatan": "Alak", "kelurahans": ["Manutapen", "Alak", "Nunbaun Delha", "Bello", "Naimata"]},
                {"namaKecamatan": "Maulafa", "kelurahans": ["Maulafa", "Kolhua", "Merdeka", "Nunhila", "Oebobo"]},
                {"namaKecamatan": "Kota Raja", "kelurahans": ["Bakunase", "Bakunase II", "Nunbaun Sabu", "Fontein", "Lasiana"]}
            ],
            "Kab. Sabu Raijua": [
                {"namaKecamatan": "Sabu Barat", "kelurahans": ["Lamboya", "Kota Waikabubak", "Kapakna", "Kota Karuni", "Ledeana"]},
                {"namaKecamatan": "Sabu Tengah", "kelurahans": ["Kotalimbu", "Ledeana", "Raba Boko", "Matawai Maringu", "Matawai Kalada"]},
                {"namaKecamatan": "Sabu Timur", "kelurahans": ["Wolwara", "Kokiwawi", "Rabaraba", "Kotakeo", "Kotahawu"]},
                {"namaKecamatan": "Loli", "kelurahans": ["Wolowae", "Loli Dua", "Loli", "Raba Bokas", "Matawai Paobok"]},
                {"namaKecamatan": "Wewewa Utara", "kelurahans": ["Wolowae", "Matawai Maringu", "Ledeana", "Kota Karuni", "Lamboya"]}
            ],
            "Kab. Timor Tengah Utara": [
                {"namaKecamatan": "Miomafo Timur", "kelurahans": ["Noelelo", "Noebesi", "Nunmafo", "Nunmafo Timur", "Nunbena"]},
                {"namaKecamatan": "Miomafo Barat", "kelurahans": ["Noemeto", "Nunmelet", "Noemuke", "Nunbena", "Nunmafo Barat"]},
                {"namaKecamatan": "Biboki Selatan", "kelurahans": ["Noemutin", "Tublopo", "Kualin", "Biboki Moenlelong", "Biboki Tanpah"]},
                {"namaKecamatan": "Biboki Utara", "kelurahans": ["Nunlelo", "Sekokatimbing", "Biboki Nilulat", "Sifani", "Kualin"]},
                {"namaKecamatan": "Insana", "kelurahans": ["Insana", "Insana Utara", "Insana Fafinesu", "Insana Tengah", "Insana Barat"]}
            ]
        }

        for kabupaten in kabupaten_objects:
            kecamatan_data = kecamatan_kelurahan_data.get(kabupaten.nama, [])
            
            for kec_data in kecamatan_data:
                try:
                    # Attempt to create with the model field name
                    kecamatan, created = Kecamatan.objects.get_or_create(
                        idKabupaten=kabupaten,
                        nama=kec_data["namaKecamatan"],
                        defaults={'nama': kec_data["namaKecamatan"]}
                    )
                except:
                    # If that fails, try using raw SQL
                    with connection.cursor() as cursor:
                        # Check if the kecamatan already exists
                        cursor.execute(
                            "SELECT idKecamatan FROM core_kecamatan WHERE nama = %s AND kabupaten_id = %s",
                            [kec_data["namaKecamatan"], kabupaten.idKabupaten]
                        )
                        row = cursor.fetchone()
                        if row:
                            # Kecamatan already exists
                            kecamatan = Kecamatan.objects.get(idKecamatan=row[0])
                            created = False
                        else:
                            # Create new kecamatan
                            cursor.execute(
                                "INSERT INTO core_kecamatan (nama, kabupaten_id) VALUES (%s, %s)",
                                [kec_data["namaKecamatan"], kabupaten.idKabupaten]
                            )
                            # Get the ID of the newly inserted record
                            kecamatan_id = cursor.lastrowid
                            kecamatan = Kecamatan.objects.get(idKecamatan=kecamatan_id)
                            created = True
                
                if created:
                    self.stdout.write(self.style.SUCCESS(f'Created Kecamatan: {kecamatan.nama}'))
                else:
                    self.stdout.write(self.style.WARNING(f'Kecamatan already exists: {kecamatan.nama}'))

                # Create Kelurahan for this Kecamatan
                for kelurahan_nama in kec_data["kelurahans"]:
                    try:
                        # Attempt to create with the model field name
                        kelurahan, created = Kelurahan.objects.get_or_create(
                            idKecamatan=kecamatan,
                            nama=kelurahan_nama,
                            defaults={'nama': kelurahan_nama}
                        )
                    except:
                        # If that fails, try using raw SQL
                        with connection.cursor() as cursor:
                            # Check if the kelurahan already exists
                            cursor.execute(
                                "SELECT idKelurahan FROM core_kelurahan WHERE nama = %s AND kecamatan_id = %s",
                                [kelurahan_nama, kecamatan.idKecamatan]
                            )
                            row = cursor.fetchone()
                            if row:
                                # Kelurahan already exists
                                kelurahan = Kelurahan.objects.get(idKelurahan=row[0])
                                created = False
                            else:
                                # Create new kelurahan
                                cursor.execute(
                                    "INSERT INTO core_kelurahan (nama, kecamatan_id) VALUES (%s, %s)",
                                    [kelurahan_nama, kecamatan.idKecamatan]
                                )
                                # Get the ID of the newly inserted record
                                kelurahan_id = cursor.lastrowid
                                kelurahan = Kelurahan.objects.get(idKelurahan=kelurahan_id)
                                created = True
                    
                    if created:
                        self.stdout.write(self.style.SUCCESS(f'Created Kelurahan: {kelurahan.nama}'))
                    else:
                        self.stdout.write(self.style.WARNING(f'Kelurahan already exists: {kelurahan.nama}'))

        self.stdout.write(
            self.style.SUCCESS('Successfully seeded wilayah data for NTT')
        )