from django.shortcuts import render, redirect
from django.db.models import Sum, Count, Q
from django.db.models.functions import Extract
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
import json
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.http import JsonResponse
from django.db import transaction
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import check_password
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.urls import reverse
from functools import wraps  # Added for custom decorator

from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from io import BytesIO

from .models import Pelanggan, Sopir, Kendaraan, Produk, StokMasuk, Pemesanan, DetailPemesanan, Feedback
from .forms import SopirEditPengirimanForm, PelangganRegisterForm, PelangganLoginForm, PemesananCheckoutForm, PelangganUpdateForm, ChangePasswordForm

def get_indonesian_date():
    """
    Get current date in Indonesian format: Kupang, Day Month Year
    Example: Kupang, 8 Januari 2026
    """
    now = datetime.now()
    indonesian_months = [
        'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
        'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
    ]
    day = now.day
    month_name = indonesian_months[now.month - 1]
    year = now.year
    return f"{day} {month_name} {year}"


def pelanggan_login_required(view_func):
    """
    Custom decorator to check if pelanggan is logged in via session.
    Redirects to login page if not authenticated.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Check if pelanggan_id exists in session
        if not request.session.get('pelanggan_id'):
            messages.error(request, 'Silakan login terlebih dahulu.')
            return redirect('pelanggan_login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def format_rupiah(amount):
    if amount is None:
        return "Rp 0"
    return f"Rp {int(amount):,}".replace(",", ".")

def add_page_template(canvas, doc, title):
    """Add header and footer to each page"""
    canvas.saveState()
    
    # Header
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawCentredString(A4[0]/2, A4[1]-50, f"Laporan {title} VIQUAM")
    
    # Footer
    canvas.setFont("Helvetica", 10)
    current_date = timezone.now().strftime("%d %B %Y")
    canvas.drawCentredString(A4[0]/2, 30, f"Tanggal Cetak: {current_date}")
    
    canvas.restoreState()

def create_pdf_header(canvas, title, date_range=None):
    """Create PDF header with date range"""
    # Header
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawCentredString(A4[0]/2, A4[1]-50, f"Laporan {title} VIQUAM")
    
    # Date range if provided
    if date_range:
        canvas.setFont("Helvetica", 10)
        canvas.drawCentredString(A4[0]/2, A4[1]-70, f"Periode: {date_range}")
    
    # Footer
    canvas.setFont("Helvetica", 10)
    current_date = timezone.now().strftime("%d %B %Y")
    canvas.drawCentredString(A4[0]/2, 30, f"Tanggal Cetak: {current_date}")

def get_dashboard_context():
    """
    Get dashboard context data without rendering template
    """
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Sum
    from decimal import Decimal
    import json
    from .models import Pemesanan, Produk, Feedback, DetailPemesanan
    
    now = timezone.now()
    
    # 1. Calculation: Start/End of Current Month
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 12:
        end_of_month = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        end_of_month = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    
    twenty_four_hours_ago = now - timedelta(hours=24)
    
    # --- Business Metrics Calculation ---
    # Pesanan Perlu Perhatian: Jumlah Pemesanan dengan status='Diproses' dan tanggalPemesanan lebih dari 24 jam yang lalu
    pesanan_perlu_perhatian = Pemesanan.objects.filter(
        status='Diproses',
        tanggalPemesanan__lte=twenty_four_hours_ago
    ).count()
    
    # Total Pesanan Diproses: Jumlah Pemesanan dengan status='Diproses'
    total_pesanan_diproses = Pemesanan.objects.filter(status='Diproses').count()
    
    # Total Pengiriman Aktif: Jumlah Pemesanan dengan status='Dikirim'
    total_pengiriman_aktif = Pemesanan.objects.filter(status='Dikirim').count()
    
    # Total Pendapatan (Bulan Ini): Total Pemesanan.total di mana status='Selesai' pada bulan berjalan
    pendapatan_bulan_ini_result = Pemesanan.objects.filter(
        status='Selesai',
        tanggalPemesanan__gte=start_of_month,
        tanggalPemesanan__lt=end_of_month
    ).aggregate(Sum('total'))['total__sum']
    
    pendapatan_bulan_ini = pendapatan_bulan_ini_result if pendapatan_bulan_ini_result is not None else Decimal('0')
    
    # Total Pendapatan (Keseluruhan): Total Pemesanan.total di mana status='Selesai' (tanpa filter tanggal)
    total_pendapatan_keseluruhan_result = Pemesanan.objects.filter(
        status='Selesai'
    ).aggregate(Sum('total'))['total__sum']
    
    total_pendapatan_keseluruhan = total_pendapatan_keseluruhan_result if total_pendapatan_keseluruhan_result is not None else Decimal('0')
    
    # Transaksi Selesai (Bulan Ini): Jumlah Pemesanan di mana status='Selesai' pada bulan berjalan
    transaksi_selesai_bulan_ini = Pemesanan.objects.filter(
        status='Selesai',
        tanggalPemesanan__gte=start_of_month,
        tanggalPemesanan__lt=end_of_month
    ).count()
    
    # Transaksi Selesai (Keseluruhan): Jumlah Pemesanan di mana status='Selesai' (tanpa filter tanggal)
    transaksi_selesai_keseluruhan = Pemesanan.objects.filter(
        status='Selesai'
    ).count()
    
    # Produk Stok Habis: Jumlah Produk dengan stok = 0
    produk_stok_habis = Produk.objects.filter(stok=0).count()
    
    # Feedback Terbaru: 1-2 entri terbaru dari model Feedback
    feedback_terbaru = Feedback.objects.all().order_by('-tanggal')[:2]
    
    # --- 6-Month Revenue Data (Chart) ---
    months = []
    current_date = now.replace(day=1)
    for i in range(6):
        months.insert(0, (current_date.month, current_date.year))
        if current_date.month == 1:
            current_date = current_date.replace(year=current_date.year - 1, month=12)
        else:
            current_date = current_date.replace(month=current_date.month - 1)
            
    start_date_filter = current_date.replace(day=1)
    
    from django.db.models.functions import Extract
    revenue_data = Pemesanan.objects.filter(
        status='Selesai',
        tanggalPemesanan__gte=start_date_filter
    ).annotate(
        month=Extract('tanggalPemesanan', 'month'),
        year=Extract('tanggalPemesanan', 'year')
    ).values('month', 'year').annotate(revenue=Sum('total')).order_by('year', 'month')
    
    chart_labels = []
    chart_data = []
    month_names = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    
    for month, year in months:
        label = f"{month_names[month-1]} {str(year)[2:]}"
        chart_labels.append(label)
        
        revenue = 0.0
        for item in revenue_data:
            if item.get('month') == month and item.get('year') == year:
                # Konversi Decimal ke float secara eksplisit
                revenue = float(item.get('revenue')) if item.get('revenue') is not None else 0.0
                break
        chart_data.append(revenue)
    
    # --- Product Sales Data (Bar Chart) ---
    # Get all products
    all_products = Produk.objects.all()
    
    # Get sales data for completed orders
    product_sales = DetailPemesanan.objects.filter(
        idPemesanan__status='Selesai'
    ).values('idProduk__namaProduk').annotate(total_sold=Sum('jumlah')).order_by('idProduk__namaProduk')
    
    # Create dictionaries for easy lookup
    sales_dict = {item['idProduk__namaProduk']: item['total_sold'] for item in product_sales}
    
    # Prepare data for chart
    product_labels = []
    product_sales_data = []
    
    for product in all_products:
        product_labels.append(product.namaProduk)
        product_sales_data.append(sales_dict.get(product.namaProduk, 0))
    
    # Convert to JSON strings
    product_labels_json = json.dumps(product_labels)
    product_sales_data_json = json.dumps(product_sales_data)

    # PENTING: Konversi data ke JSON string dan kirim ke context
    chart_labels_json = json.dumps(chart_labels)
    chart_data_json = json.dumps(chart_data)

    context = {
        'pesanan_perlu_perhatian': pesanan_perlu_perhatian,
        'total_pesanan_diproses': total_pesanan_diproses,
        'total_pengiriman_aktif': total_pengiriman_aktif,
        'total_pendapatan_keseluruhan': total_pendapatan_keseluruhan,
        'transaksi_selesai_keseluruhan': transaksi_selesai_keseluruhan,
        'produk_stok_habis': produk_stok_habis,
        'feedback_terbaru': feedback_terbaru,
        # Kirim string JSON
        'chart_labels_json': chart_labels_json,
        'chart_data_json': chart_data_json,
        'product_labels_json': product_labels_json,
        'product_sales_data_json': product_sales_data_json,
        'twenty_four_hours_ago': twenty_four_hours_ago.strftime('%Y-%m-%d')
    }
    
    return context

# Preview views
def admin_dashboard(request):
    context = get_dashboard_context()
    return render(request, 'core/dashboard.html', context)
def admin_laporan_pelanggan(request):
    # Get filter parameters
    tgl_mulai = request.GET.get('tgl_mulai')
    tgl_akhir = request.GET.get('tgl_akhir')
    
    # Build queryset
    pelanggan_list = Pelanggan.objects.all()
    
    # Apply date filters if provided and not empty
    if tgl_mulai and tgl_akhir:
        # Filter pelanggan based on their last order date
        pelanggan_dengan_pesanan = Pemesanan.objects.filter(
            tanggalPemesanan__date__gte=tgl_mulai,
            tanggalPemesanan__date__lte=tgl_akhir
        ).values_list('idPelanggan', flat=True)
        pelanggan_list = pelanggan_list.filter(idPelanggan__in=pelanggan_dengan_pesanan)
    
    # Calculate transaction statistics for each customer (only 'Selesai' orders)
    pelanggan_data = []
    for pelanggan in pelanggan_list:
        # Count completed transactions
        jml_transaksi = Pemesanan.objects.filter(idPelanggan=pelanggan, status='Selesai').count()
        
        # Calculate total purchases from completed transactions only
        total_pembelian = Pemesanan.objects.filter(idPelanggan=pelanggan, status='Selesai').aggregate(
            total=Sum('total')
        )['total'] or 0
        
        pelanggan_data.append({
            'nama': pelanggan.nama,
            'noWa': pelanggan.noWa,
            'alamat': pelanggan.alamat,
            'username': pelanggan.username,
            'jml_transaksi': jml_transaksi,
            'total_pembelian': format_rupiah(total_pembelian)
        })
    
    context = {
        'judul_laporan': 'Data Pelanggan',
        'pelanggan_list': pelanggan_data,
        'tgl_mulai': tgl_mulai,
        'tgl_akhir': tgl_akhir
    }
    return render(request, 'core/laporan_pelanggan.html', context)

def admin_laporan_produk(request):
    filter_tipe = request.GET.get('filter_tipe')
    batas_stok = request.GET.get('batas_stok', 10)
    tgl_mulai = request.GET.get('tgl_mulai')
    tgl_akhir = request.GET.get('tgl_akhir')
    
    produk_list = Produk.objects.all()
    
    if filter_tipe == 'terlaris' or (tgl_mulai or tgl_akhir):
        date_filter_q = None
        if tgl_mulai and tgl_akhir:
            date_filter_q = Q(detailpemesanan__idPemesanan__tanggalPemesanan__date__gte=tgl_mulai) & \
                           Q(detailpemesanan__idPemesanan__tanggalPemesanan__date__lte=tgl_akhir)
        elif tgl_mulai:
            date_filter_q = Q(detailpemesanan__idPemesanan__tanggalPemesanan__date__gte=tgl_mulai)
        elif tgl_akhir:
            date_filter_q = Q(detailpemesanan__idPemesanan__tanggalPemesanan__date__lte=tgl_akhir)
        
        if filter_tipe == 'terlaris':
            if date_filter_q:
                produk_list = produk_list.annotate(
                    total_terjual=Sum('detailpemesanan__jumlah', filter=date_filter_q)
                ).order_by('-total_terjual')
            else:
                produk_list = produk_list.annotate(
                    total_terjual=Sum('detailpemesanan__jumlah')
                ).order_by('-total_terjual')
        else:
            produk_list = produk_list.annotate(
                total_terjual=Sum('detailpemesanan__jumlah', filter=date_filter_q) if date_filter_q else Sum('detailpemesanan__jumlah')
            )
    elif filter_tipe == 'stok_menipis':
        produk_list = produk_list.filter(stok__lte=batas_stok).order_by('stok')
    
    produk_data = []
    for produk in produk_list:
        product_date_filter_q = None
        if tgl_mulai and tgl_akhir:
            product_date_filter_q = Q(idPemesanan__tanggalPemesanan__date__gte=tgl_mulai) & \
                                  Q(idPemesanan__tanggalPemesanan__date__lte=tgl_akhir)
        elif tgl_mulai:
            product_date_filter_q = Q(idPemesanan__tanggalPemesanan__date__gte=tgl_mulai)
        elif tgl_akhir:
            product_date_filter_q = Q(idPemesanan__tanggalPemesanan__date__lte=tgl_akhir)
            
        total_terjual = 0
        if filter_tipe == 'terlaris' or (tgl_mulai or tgl_akhir):
            total_terjual_queryset = DetailPemesanan.objects.filter(idProduk=produk)
            if product_date_filter_q:
                total_terjual_queryset = total_terjual_queryset.filter(product_date_filter_q)
            total_terjual = total_terjual_queryset.aggregate(total=Sum('jumlah'))['total'] or 0
        
        produk_data.append({
            'namaProduk': produk.namaProduk,
            'ukuranKemasan': produk.ukuranKemasan,
            'hargaPerDus': format_rupiah(produk.hargaPerDus),
            'stok': produk.stok,
            'total_terjual': total_terjual if (filter_tipe == 'terlaris' or (tgl_mulai or tgl_akhir)) else None
        })
    
    context = {
        'judul_laporan': 'Produk & Stok',
        'produk_list': produk_data,
        'tgl_mulai': tgl_mulai,
        'tgl_akhir': tgl_akhir,
        'filter_tipe': filter_tipe,
        'batas_stok': batas_stok
    }
    return render(request, 'core/laporan_produk.html', context)

def admin_laporan_sopir_kendaraan(request):
    # Get filter parameters
    tgl_mulai = request.GET.get('tgl_mulai')
    tgl_akhir = request.GET.get('tgl_akhir')
    
    # Build queryset
    sopir_list = Sopir.objects.all()
    
    # Process data for each driver
    sopir_data = []
    for sopir in sopir_list:
        # Get driver's vehicle
        kendaraan = Kendaraan.objects.filter(idSopir=sopir).first()
        kendaraan_nama = kendaraan.nama if kendaraan else None
        
        # Count completed orders for this driver
        pesanan_selesai_queryset = Pemesanan.objects.filter(
            idSopir=sopir,
            status='Selesai'
        )
        
        # Apply date filters if provided and not empty
        if tgl_mulai:
            pesanan_selesai_queryset = pesanan_selesai_queryset.filter(
                tanggalPemesanan__date__gte=tgl_mulai
            )
        if tgl_akhir:
            pesanan_selesai_queryset = pesanan_selesai_queryset.filter(
                tanggalPemesanan__date__lte=tgl_akhir
            )
            
        pesanan_selesai = pesanan_selesai_queryset.count()
        
        sopir_data.append({
            'nama': sopir.nama,
            'noHp': sopir.noHp,
            'username': sopir.username,
            'kendaraan_nama': kendaraan_nama,
            'pesanan_selesai': pesanan_selesai
        })
    
    context = {
        'judul_laporan': 'Sopir & Kendaraan',
        'sopir_list': sopir_data,
        'tgl_mulai': tgl_mulai,
        'tgl_akhir': tgl_akhir
    }
    return render(request, 'core/laporan_sopir_kendaraan.html', context)

def admin_laporan_pemesanan_pendapatan(request):
    # Get filter parameters
    tgl_mulai = request.GET.get('tgl_mulai')
    tgl_akhir = request.GET.get('tgl_akhir')
    status_pesanan = request.GET.get('status_pesanan')
    
    # Build queryset
    pemesanan_list = Pemesanan.objects.all()
    
    # Apply filters
    if tgl_mulai:
        pemesanan_list = pemesanan_list.filter(
            tanggalPemesanan__date__gte=tgl_mulai
        )
    if tgl_akhir:
        pemesanan_list = pemesanan_list.filter(
            tanggalPemesanan__date__lte=tgl_akhir
        )
    
    if status_pesanan:
        pemesanan_list = pemesanan_list.filter(status=status_pesanan)
    
    # Calculate total revenue - only from 'Selesai' orders
    pendapatan_queryset = Pemesanan.objects.filter(status='Selesai')
    
    # Apply the same date filters to pendapatan queryset
    if tgl_mulai:
        pendapatan_queryset = pendapatan_queryset.filter(
            tanggalPemesanan__date__gte=tgl_mulai
        )
    if tgl_akhir:
        pendapatan_queryset = pendapatan_queryset.filter(
            tanggalPemesanan__date__lte=tgl_akhir
        )
    
    # If status filter is applied and it's 'Selesai', use the same queryset
    if status_pesanan == 'Selesai':
        total_pendapatan = pemesanan_list.aggregate(total=Sum('total'))['total'] or 0
    else:
        # Otherwise, calculate from 'Selesai' orders separately
        total_pendapatan = pendapatan_queryset.aggregate(total=Sum('total'))['total'] or 0
    
    # Process data for each order
    pemesanan_data = []
    for pemesanan in pemesanan_list:
        # Get product details for this order
        detail_pemesanan_list = DetailPemesanan.objects.filter(idPemesanan=pemesanan)
        produk_details = []
        for detail in detail_pemesanan_list:
            produk_details.append(f"{detail.idProduk.namaProduk} ({detail.jumlah} {detail.idProduk.satuan})")
        daftar_barang = ', '.join(produk_details)
        
        pemesanan_data.append({
            'tanggalPemesanan': pemesanan.tanggalPemesanan,
            'idPelanggan': pemesanan.idPelanggan,
            'daftar_barang': daftar_barang,
            'alamatPengiriman': pemesanan.alamatPengiriman,
            'status': pemesanan.status,
            'total': format_rupiah(pemesanan.total)
        })
    
    context = {
        'judul_laporan': 'Pemesanan & Pendapatan',
        'pemesanan_list': pemesanan_data,
        'tgl_mulai': tgl_mulai,
        'tgl_akhir': tgl_akhir,
        'status_pesanan': status_pesanan,
        'total_pendapatan': format_rupiah(total_pendapatan)
    }
    return render(request, 'core/laporan_pemesanan_pendapatan.html', context)

def admin_laporan_feedback(request):
    # Get filter parameters
    tgl_mulai = request.GET.get('tgl_mulai')
    tgl_akhir = request.GET.get('tgl_akhir')
    
    # Build queryset
    feedback_list = Feedback.objects.all().select_related('idPelanggan')
    
    # Apply date filters if provided and not empty
    if tgl_mulai:
        feedback_list = feedback_list.filter(
            tanggal__date__gte=tgl_mulai
        )
    if tgl_akhir:
        feedback_list = feedback_list.filter(
            tanggal__date__lte=tgl_akhir
        )
    
    # Process data for each feedback
    feedback_data = []
    for feedback in feedback_list:
        feedback_data.append({
            'tanggal': feedback.tanggal,
            'idPelanggan': feedback.idPelanggan,
            'isi': feedback.isi
        })
    
    context = {
        'judul_laporan': 'Feedback Pelanggan',
        'feedback_list': feedback_data,
        'tgl_mulai': tgl_mulai,
        'tgl_akhir': tgl_akhir
    }
    return render(request, 'core/laporan_feedback.html', context)

def laporan_pelanggan(request):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="laporan_pelanggan.pdf"'
    
    # Create a PDF buffer
    buffer = BytesIO()
    
    # Create the PDF object, using the buffer as its "file."
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                           leftMargin=2*cm, rightMargin=2*cm,
                           topMargin=2*cm, bottomMargin=2*cm)
    
    # Get filter parameters
    tgl_mulai = request.GET.get('tgl_mulai')
    tgl_akhir = request.GET.get('tgl_akhir')
    
    # Build queryset
    pelanggan_list = Pelanggan.objects.all()
    
    # Apply date filters if provided and not empty
    date_range = ""
    if tgl_mulai and tgl_akhir:
        date_range = f"{tgl_mulai} - {tgl_akhir}"
        # Filter pelanggan based on their last order date
        pelanggan_dengan_pesanan = Pemesanan.objects.filter(
            tanggalPemesanan__date__gte=tgl_mulai,
            tanggalPemesanan__date__lte=tgl_akhir
        ).values_list('idPelanggan', flat=True)
        pelanggan_list = pelanggan_list.filter(idPelanggan__in=pelanggan_dengan_pesanan)
    
    # Container for the 'Flowable' objects
    story = []
    
    # Add company header
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    normal_style = styles['Normal']
    
    # Set font sizes for title
    title_style.fontSize = 14
    title_style.fontName = 'Helvetica-Bold'
    title_style.alignment = 1  # Center alignment
    
    # Company name
    company_name = Paragraph("<b>PT VIQUAM KUPANG</b>", title_style)
    story.append(company_name)
    
    # Company address
    address_style = normal_style.clone('Address')
    address_style.fontSize = 9  # Set font size to 9pt
    address_style.alignment = 1  # Center alignment
    address = Paragraph("Jl. Cendrawasih, Lahilai Bissi Kopan, Kec. Kota Lama, Kota Kupang, Nusa Tenggara Timur", address_style)
    story.append(address)
    
    # Contact information
    contact_style = normal_style.clone('Contact')
    contact_style.fontSize = 9  # Set font size to 9pt
    contact_style.alignment = 1  # Center alignment
    contact = Paragraph("Telp: 2349076", contact_style)
    story.append(contact)
    
    # Date range if provided
    if date_range:
        date_paragraph = Paragraph(f"Periode: {date_range}", address_style)
        story.append(date_paragraph)
    
    # Add spacer between address/date and horizontal line
    story.append(Spacer(1, 12))
    
    # Double horizontal line (moved above table)
    # Using a 1x1 table for reliable horizontal line placement
    line_table = Table([['']], colWidths=[16*cm], rowHeights=[1])
    line_table.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (0, 0), 2, colors.black),  # Top line
        ('LINEBELOW', (0, 0), (0, 0), 1, colors.black),  # Bottom line
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 0),
        ('TOPPADDING', (0, 0), (0, 0), 0),
        ('BOTTOMPADDING', (0, 0), (0, 0), 0),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 12))
    
    # Add report title
    report_title_style = normal_style.clone('ReportTitle')
    report_title_style.fontSize = 12
    report_title_style.alignment = 1  # Center alignment
    report_title_style.fontName = 'Helvetica-Bold'
    report_title = Paragraph("LAPORAN DATA PELANGGAN", report_title_style)
    story.append(report_title)
    
    # Add filter information
    filter_info_style = normal_style.clone('FilterInfo')
    filter_info_style.fontSize = 9
    filter_info_style.alignment = 1  # Center alignment
    
    # Status filter info - Not applicable for this report, just show date range
    if date_range:
        date_filter_paragraph = Paragraph(f"Periode: {date_range}", filter_info_style)
        story.append(date_filter_paragraph)
    
    story.append(Spacer(1, 12))
    
    # Prepare data for table with text wrapping
    # Create header style for wrapping
    header_style = normal_style.clone('HeaderStyle')
    header_style.fontSize = 10
    header_style.alignment = 1  # Center alignment
    header_style.fontName = 'Helvetica-Bold'
    
    data = [[
        Paragraph('No.', header_style),
        Paragraph('Nama', header_style),
        Paragraph('No WA', header_style),
        Paragraph('Alamat', header_style),
        Paragraph('Username', header_style),
        Paragraph('Jml Transaksi', header_style),
        Paragraph('Total Pembelian', header_style)
    ]]
    
    for i, pelanggan in enumerate(pelanggan_list, 1):
        # Calculate transaction statistics for this customer (only 'Selesai' orders)
        jml_transaksi = Pemesanan.objects.filter(idPelanggan=pelanggan, status='Selesai').count()
        total_pembelian = Pemesanan.objects.filter(idPelanggan=pelanggan, status='Selesai').aggregate(
            total=Sum('total')
        )['total'] or 0
        
        # Create paragraph object for address text wrapping
        alamat_paragraph = Paragraph(pelanggan.alamat, normal_style)
        
        row = [
            str(i),
            pelanggan.nama,
            pelanggan.noWa,
            alamat_paragraph,  # Use paragraph for text wrapping
            pelanggan.username,
            str(jml_transaksi),
            format_rupiah(total_pembelian)
        ]
        data.append(row)
    
    # Create table with improved styling and adjusted column widths
    table = Table(data, colWidths=[1*cm, 3*cm, 2.5*cm, 3.5*cm, 2.5*cm, 2*cm, 2.5*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    story.append(table)
    story.append(Spacer(1, 24))
    
    # Add signature section (positioned at bottom right)
    story.append(Spacer(1, 200))  # Push signature to bottom
    current_date = get_indonesian_date()
    signature_data = [
        ['', f'Kupang, {current_date}'],
        ['', 'Mengetahui,'],
        ['', 'Pimpinan PT Viquam Kupang'],
        ['', ''],
        ['', '(Alain N. Susanto)']
    ]
    
    signature_table = Table(signature_data, colWidths=[8*cm, 8*cm])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (1, -1), (1, -1), 30),
    ]))
    
    story.append(signature_table)
    
    # Build PDF
    doc.build(story)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response

def laporan_produk(request):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="laporan_produk.pdf"'
    
    # Create a PDF buffer
    buffer = BytesIO()
    
    # Create the PDF object, using the buffer as its "file."
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                           leftMargin=2*cm, rightMargin=2*cm,
                           topMargin=2*cm, bottomMargin=2*cm)
    
    filter_tipe = request.GET.get('filter_tipe')
    batas_stok = request.GET.get('batas_stok', 10)
    tgl_mulai = request.GET.get('tgl_mulai')
    tgl_akhir = request.GET.get('tgl_akhir')
    
    produk_list = Produk.objects.all()
    
    date_range = ""
    if tgl_mulai and tgl_akhir:
        date_range = f"{tgl_mulai} - {tgl_akhir}"
    
    # Container for the 'Flowable' objects
    story = []
    
    # Add company header
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    normal_style = styles['Normal']
    
    # Set font sizes for title
    title_style.fontSize = 14
    title_style.fontName = 'Helvetica-Bold'
    title_style.alignment = 1  # Center alignment
    
    # Company name
    company_name = Paragraph("<b>PT VIQUAM KUPANG</b>", title_style)
    story.append(company_name)
    
    # Company address
    address_style = normal_style.clone('Address')
    address_style.fontSize = 9  # Set font size to 9pt
    address_style.alignment = 1  # Center alignment
    address = Paragraph("Jl. Cendrawasih, Lahilai Bissi Kopan, Kec. Kota Lama, Kota Kupang, Nusa Tenggara Timur", address_style)
    story.append(address)
    
    # Contact information
    contact_style = normal_style.clone('Contact')
    contact_style.fontSize = 9  # Set font size to 9pt
    contact_style.alignment = 1  # Center alignment
    contact = Paragraph("Telp: 2349076", contact_style)
    story.append(contact)
    
    # Date range if provided
    if date_range:
        date_paragraph = Paragraph(f"Periode: {date_range}", address_style)
        story.append(date_paragraph)
    
    # Add spacer between address/date and horizontal line
    story.append(Spacer(1, 12))
    
    # Double horizontal line (moved above table)
    # Using a 1x1 table for reliable horizontal line placement
    line_table = Table([['']], colWidths=[16*cm], rowHeights=[1])
    line_table.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (0, 0), 2, colors.black),  # Top line
        ('LINEBELOW', (0, 0), (0, 0), 1, colors.black),  # Bottom line
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 0),
        ('TOPPADDING', (0, 0), (0, 0), 0),
        ('BOTTOMPADDING', (0, 0), (0, 0), 0),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 12))
    
    # Add report title
    report_title_style = normal_style.clone('ReportTitle')
    report_title_style.fontSize = 12
    report_title_style.alignment = 1  # Center alignment
    report_title_style.fontName = 'Helvetica-Bold'
    report_title = Paragraph("LAPORAN MUTASI STOK PRODUK", report_title_style)
    story.append(report_title)
    
    # Add filter information
    filter_info_style = normal_style.clone('FilterInfo')
    filter_info_style.fontSize = 9
    filter_info_style.alignment = 1  # Center alignment
    
    # Status filter info - Not applicable for this report, just show date range
    if date_range:
        date_filter_paragraph = Paragraph(f"Periode: {date_range}", filter_info_style)
        story.append(date_filter_paragraph)
    
    story.append(Spacer(1, 12))
    
    # Prepare data for table
    data = [['No.', 'Nama Produk', 'Stok Awal', 'Masuk', 'Keluar', 'Stok Akhir', 'Satuan']]
    
    # Calculate stock mutations for each product
    for i, produk in enumerate(produk_list, 1):
        # Calculate Barang Masuk (from StokMasuk table within date range)
        masuk_query = StokMasuk.objects.filter(idProduk=produk)
        if tgl_mulai and tgl_akhir:
            masuk_query = masuk_query.filter(tanggal__range=[tgl_mulai, tgl_akhir])
        elif tgl_mulai:
            masuk_query = masuk_query.filter(tanggal__gte=tgl_mulai)
        elif tgl_akhir:
            masuk_query = masuk_query.filter(tanggal__lte=tgl_akhir)
        
        total_masuk = masuk_query.aggregate(total=Sum('jumlah'))['total'] or 0
        
        # Calculate Barang Keluar (from DetailPemesanan with completed orders within date range)
        keluar_query = DetailPemesanan.objects.filter(idProduk=produk)
        
        # Join with Pemesanan table to filter by status
        keluar_query = keluar_query.select_related('idPemesanan')
        
        # Filter by order status (completed orders only)
        completed_orders_filter = Q(idPemesanan__status='Selesai') | Q(idPemesanan__status='Dikirim')
        keluar_query = keluar_query.filter(completed_orders_filter)
        
        if tgl_mulai and tgl_akhir:
            keluar_query = keluar_query.filter(idPemesanan__tanggalPemesanan__date__range=[tgl_mulai, tgl_akhir])
        elif tgl_mulai:
            keluar_query = keluar_query.filter(idPemesanan__tanggalPemesanan__date__gte=tgl_mulai)
        elif tgl_akhir:
            keluar_query = keluar_query.filter(idPemesanan__tanggalPemesanan__date__lte=tgl_akhir)
        
        total_keluar = keluar_query.aggregate(total=Sum('jumlah'))['total'] or 0
        
        # Calculate Stok Awal using the formula: Stok Awal = Stok Akhir - Total Masuk + Total Keluar
        stok_akhir = produk.stok
        stok_awal = stok_akhir - total_masuk + total_keluar
        
        row = [
            str(i),
            produk.namaProduk,
            str(stok_awal),
            str(total_masuk),
            str(total_keluar),
            str(stok_akhir),
            produk.satuan
        ]
        data.append(row)
    
    # Create table with improved styling
    table = Table(data, colWidths=[1*cm, 4*cm, 2*cm, 1.5*cm, 1.5*cm, 2*cm, 1.5*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    story.append(table)
    story.append(Spacer(1, 24))
    
    # Add signature section (positioned at bottom right)
    story.append(Spacer(1, 200))  # Push signature to bottom
    current_date = get_indonesian_date()
    signature_data = [
        ['', f'Kupang, {current_date}'],
        ['', 'Mengetahui,'],
        ['', 'Pimpinan PT Viquam Kupang'],
        ['', ''],
        ['', '(Alain N. Susanto)']
    ]
    
    signature_table = Table(signature_data, colWidths=[8*cm, 8*cm])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (1, -1), (1, -1), 30),
    ]))
    
    story.append(signature_table)
    
    # Build PDF
    doc.build(story)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response

def laporan_sopir_kendaraan(request):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="laporan_sopir_kendaraan.pdf"'
    
    # Create a PDF buffer
    buffer = BytesIO()
    
    # Create the PDF object, using the buffer as its "file."
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                           leftMargin=2*cm, rightMargin=2*cm,
                           topMargin=2*cm, bottomMargin=2*cm)
    
    # Get filter parameters
    tgl_mulai = request.GET.get('tgl_mulai')
    tgl_akhir = request.GET.get('tgl_akhir')
    
    # Build queryset
    sopir_list = Sopir.objects.all()
    
    # Apply date filters if provided and not empty
    date_range = ""
    if tgl_mulai and tgl_akhir:
        date_range = f"{tgl_mulai} - {tgl_akhir}"
    
    # Container for the 'Flowable' objects
    story = []
    
    # Add company header
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    normal_style = styles['Normal']
    
    # Set font sizes for title
    title_style.fontSize = 14
    title_style.fontName = 'Helvetica-Bold'
    title_style.alignment = 1  # Center alignment
    
    # Company name
    company_name = Paragraph("<b>PT VIQUAM KUPANG</b>", title_style)
    story.append(company_name)
    
    # Company address
    address_style = normal_style.clone('Address')
    address_style.fontSize = 9  # Set font size to 9pt
    address_style.alignment = 1  # Center alignment
    address = Paragraph("Jl. Cendrawasih, Lahilai Bissi Kopan, Kec. Kota Lama, Kota Kupang, Nusa Tenggara Timur", address_style)
    story.append(address)
    
    # Contact information
    contact_style = normal_style.clone('Contact')
    contact_style.fontSize = 9  # Set font size to 9pt
    contact_style.alignment = 1  # Center alignment
    contact = Paragraph("Telp: 2349076", contact_style)
    story.append(contact)
    
    # Date range if provided
    if date_range:
        date_paragraph = Paragraph(f"Periode: {date_range}", address_style)
        story.append(date_paragraph)
    
    # Add spacer between address/date and horizontal line
    story.append(Spacer(1, 12))
    
    # Double horizontal line (moved above table)
    # Using a 1x1 table for reliable horizontal line placement
    line_table = Table([['']], colWidths=[16*cm], rowHeights=[1])
    line_table.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (0, 0), 2, colors.black),  # Top line
        ('LINEBELOW', (0, 0), (0, 0), 1, colors.black),  # Bottom line
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 0),
        ('TOPPADDING', (0, 0), (0, 0), 0),
        ('BOTTOMPADDING', (0, 0), (0, 0), 0),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 12))
    
    # Add report title
    report_title_style = normal_style.clone('ReportTitle')
    report_title_style.fontSize = 12
    report_title_style.alignment = 1  # Center alignment
    report_title_style.fontName = 'Helvetica-Bold'
    report_title = Paragraph("LAPORAN SOPIR & KENDARAAN", report_title_style)
    story.append(report_title)
    
    # Add filter information
    filter_info_style = normal_style.clone('FilterInfo')
    filter_info_style.fontSize = 9
    filter_info_style.alignment = 1  # Center alignment
    
    # Status filter info - Not applicable for this report, just show date range
    if date_range:
        date_filter_paragraph = Paragraph(f"Periode: {date_range}", filter_info_style)
        story.append(date_filter_paragraph)
    
    story.append(Spacer(1, 12))
    
    # Prepare data for table
    data = [['No.', 'Nama Sopir', 'No HP', 'Username', 'Kendaraan', 'Pesanan Selesai']]
    
    for i, sopir in enumerate(sopir_list, 1):
        # Get driver's vehicle
        kendaraan = Kendaraan.objects.filter(idSopir=sopir).first()
        nama_kendaraan = kendaraan.nama if kendaraan else "-"
        
        # Count completed orders for this driver
        pesanan_selesai_queryset = Pemesanan.objects.filter(
            idSopir=sopir,
            status='Selesai'
        )
        
        # Apply date filters if provided and not empty
        if tgl_mulai:
            pesanan_selesai_queryset = pesanan_selesai_queryset.filter(
                tanggalPemesanan__date__gte=tgl_mulai
            )
        if tgl_akhir:
            pesanan_selesai_queryset = pesanan_selesai_queryset.filter(
                tanggalPemesanan__date__lte=tgl_akhir
            )
            
        pesanan_selesai_count = pesanan_selesai_queryset.count()
        
        row = [
            str(i),
            sopir.nama,
            sopir.noHp,
            sopir.username,
            nama_kendaraan,
            str(pesanan_selesai_count)
        ]
        data.append(row)
    
    # Create table with improved styling
    table = Table(data, colWidths=[1.5*cm, 3*cm, 3*cm, 2.5*cm, 4*cm, 3*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    story.append(table)
    story.append(Spacer(1, 24))
    
    # Add signature section (positioned at bottom right)
    story.append(Spacer(1, 200))  # Push signature to bottom
    current_date = get_indonesian_date()
    signature_data = [
        ['', f'Kupang, {current_date}'],
        ['', 'Mengetahui,'],
        ['', 'Pimpinan PT Viquam Kupang'],
        ['', ''],
        ['', '(Alain N. Susanto)']
    ]
    
    signature_table = Table(signature_data, colWidths=[8*cm, 8*cm])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (1, -1), (1, -1), 30),
    ]))
    
    story.append(signature_table)
    
    # Build PDF
    doc.build(story)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response

def laporan_pemesanan_pendapatan(request):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="laporan_pemesanan_pendapatan.pdf"'
    
    # Create a PDF buffer
    buffer = BytesIO()
    
    # Create the PDF object, using the buffer as its "file."
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                           leftMargin=2*cm, rightMargin=2*cm,
                           topMargin=2*cm, bottomMargin=2*cm)
    
    # Get filter parameters
    tgl_mulai = request.GET.get('tgl_mulai')
    tgl_akhir = request.GET.get('tgl_akhir')
    status_pesanan = request.GET.get('status_pesanan')
    
    # Build queryset
    pemesanan_list = Pemesanan.objects.all()
    
    # Apply filters
    date_range = ""
    if tgl_mulai and tgl_akhir:
        date_range = f"{tgl_mulai} - {tgl_akhir}"
        pemesanan_list = pemesanan_list.filter(
            tanggalPemesanan__date__gte=tgl_mulai,
            tanggalPemesanan__date__lte=tgl_akhir
        )
    else:
        # Apply individual date filters if provided
        if tgl_mulai:
            pemesanan_list = pemesanan_list.filter(
                tanggalPemesanan__date__gte=tgl_mulai
            )
        if tgl_akhir:
            pemesanan_list = pemesanan_list.filter(
                tanggalPemesanan__date__lte=tgl_akhir
            )
    
    if status_pesanan:
        pemesanan_list = pemesanan_list.filter(status=status_pesanan)
    
    # Calculate total revenue - only from valid orders (Selesai)
    valid_pemesanan_list = pemesanan_list.filter(status='Selesai')
    total_pendapatan = valid_pemesanan_list.aggregate(total=Sum('total'))['total'] or 0
    
    # Container for the 'Flowable' objects
    story = []
    
    # Add company header
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    normal_style = styles['Normal']
    
    # Set font sizes for title
    title_style.fontSize = 14
    title_style.fontName = 'Helvetica-Bold'
    title_style.alignment = 1  # Center alignment
    
    # Company name
    company_name = Paragraph("<b>PT VIQUAM KUPANG</b>", title_style)
    story.append(company_name)
    
    # Company address
    address_style = normal_style.clone('Address')
    address_style.fontSize = 9  # Set font size to 9pt
    address_style.alignment = 1  # Center alignment
    address = Paragraph("Jl. Cendrawasih, Lahilai Bissi Kopan, Kec. Kota Lama, Kota Kupang, Nusa Tenggara Timur", address_style)
    story.append(address)
    
    # Contact information
    contact_style = normal_style.clone('Contact')
    contact_style.fontSize = 9  # Set font size to 9pt
    contact_style.alignment = 1  # Center alignment
    contact = Paragraph("Telp: 2349076", contact_style)
    story.append(contact)
    
    # Date range if provided
    if date_range:
        date_paragraph = Paragraph(f"Periode: {date_range}", address_style)
        story.append(date_paragraph)
    
    # Add spacer between address/date and horizontal line
    story.append(Spacer(1, 12))
    
    # Double horizontal line (moved above table)
    # Using a 1x1 table for reliable horizontal line placement
    line_table = Table([['']], colWidths=[16*cm], rowHeights=[1])
    line_table.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (0, 0), 2, colors.black),  # Top line
        ('LINEBELOW', (0, 0), (0, 0), 1, colors.black),  # Bottom line
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 0),
        ('TOPPADDING', (0, 0), (0, 0), 0),
        ('BOTTOMPADDING', (0, 0), (0, 0), 0),
    ]))
    story.append(line_table)
    
    # Add spacer after the horizontal line
    story.append(Spacer(1, 12))
    
    # Add report title
    report_title_style = normal_style.clone('ReportTitle')
    report_title_style.fontSize = 12
    report_title_style.alignment = 1  # Center alignment
    report_title_style.fontName = 'Helvetica-Bold'
    report_title = Paragraph("LAPORAN PEMESANAN & PENDAPATAN", report_title_style)
    story.append(report_title)
    
    # Add filter information
    filter_info_style = normal_style.clone('FilterInfo')
    filter_info_style.fontSize = 9
    filter_info_style.alignment = 1  # Center alignment
    
    # Status filter info
    status_label = "Semua Status"
    if status_pesanan:
        if status_pesanan == 'Diproses':
            status_label = "Diproses"
        elif status_pesanan == 'Dikirim':
            status_label = "Dikirim"
        elif status_pesanan == 'Selesai':
            status_label = "Selesai"
        elif status_pesanan == 'Dibatalkan':
            status_label = "Dibatalkan"
    
    status_paragraph = Paragraph(f"Status Pesanan: {status_label}", filter_info_style)
    story.append(status_paragraph)
    
    if date_range:
        date_filter_paragraph = Paragraph(f"Periode: {date_range}", filter_info_style)
        story.append(date_filter_paragraph)
    
    story.append(Spacer(1, 12))
    
    # Prepare data for table with text wrapping
    # Create header style for wrapping
    header_style = normal_style.clone('HeaderStyle')
    header_style.fontSize = 10
    header_style.alignment = 1  # Center alignment
    header_style.fontName = 'Helvetica-Bold'
    
    data = [[
        Paragraph('No.', header_style),
        Paragraph('Tanggal', header_style),
        Paragraph('Pelanggan', header_style),
        Paragraph('Daftar Barang', header_style),
        Paragraph('Alamat', header_style),
        Paragraph('Status', header_style),
        Paragraph('Total', header_style)
    ]]
    
    for i, pemesanan in enumerate(pemesanan_list, 1):
        # Get product details for this order
        detail_pemesanan_list = DetailPemesanan.objects.filter(idPemesanan=pemesanan)
        produk_details = []
        for detail in detail_pemesanan_list:
            produk_details.append(f"{detail.idProduk.namaProduk} ({detail.jumlah} {detail.idProduk.satuan})")
        produk_info = ', '.join(produk_details)
        
        # Create paragraph objects for text wrapping
        produk_paragraph = Paragraph(produk_info, normal_style)
        alamat_paragraph = Paragraph(pemesanan.alamatPengiriman, normal_style)
        
        row = [
            str(i),
            pemesanan.tanggalPemesanan.strftime("%d/%m/%Y"),
            pemesanan.idPelanggan.nama,
            produk_paragraph,  # Use paragraph for text wrapping
            alamat_paragraph,  # Use paragraph for text wrapping
            pemesanan.status,
            format_rupiah(pemesanan.total)
        ]
        data.append(row)
    
    # Create table with improved styling and adjusted column widths
    # Column distribution: [No, Tanggal, Pelanggan, Daftar Barang, Alamat, Status, Total]
    table = Table(data, colWidths=[1*cm, 2.5*cm, 2.5*cm, 4.5*cm, 3.5*cm, 2*cm, 2.5*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),  # Changed to TOP for better text wrapping
    ]))
    
    story.append(table)
    
    # Add total revenue summary after the table
    story.append(Spacer(1, 12))
    total_summary_style = normal_style.clone('TotalSummary')
    total_summary_style.fontSize = 10
    total_summary_style.alignment = 2  # Right alignment
    total_summary_style.fontName = 'Helvetica-Bold'
    total_paragraph = Paragraph(f"TOTAL PENDAPATAN: {format_rupiah(total_pendapatan)}", total_summary_style)
    story.append(total_paragraph)
    
    story.append(Spacer(1, 24))
    
    # Add signature section (positioned at bottom right)
    story.append(Spacer(1, 200))  # Push signature to bottom
    current_date = get_indonesian_date()
    signature_data = [
        ['', f'Kupang, {current_date}'],
        ['', 'Mengetahui,'],
        ['', 'Pimpinan PT Viquam Kupang'],
        ['', ''],
        ['', '(Alain N. Susanto)']
    ]
    
    signature_table = Table(signature_data, colWidths=[8*cm, 8*cm])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (1, -1), (1, -1), 30),
    ]))
    
    story.append(signature_table)
    
    # Build PDF
    doc.build(story)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response

def laporan_feedback(request):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="laporan_feedback.pdf"'
    
    # Create a PDF buffer
    buffer = BytesIO()
    
    # Create the PDF object, using the buffer as its "file."
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                           leftMargin=2*cm, rightMargin=2*cm,
                           topMargin=2*cm, bottomMargin=2*cm)
    
    # Get filter parameters
    tgl_mulai = request.GET.get('tgl_mulai')
    tgl_akhir = request.GET.get('tgl_akhir')
    
    # Build queryset
    feedback_list = Feedback.objects.all().select_related('idPelanggan')
    
    # Apply date filters if provided and not empty
    date_range = ""
    if tgl_mulai and tgl_akhir:
        date_range = f"{tgl_mulai} - {tgl_akhir}"
        feedback_list = feedback_list.filter(
            tanggal__date__gte=tgl_mulai,
            tanggal__date__lte=tgl_akhir
        )
    else:
        # Apply individual date filters if provided
        if tgl_mulai:
            feedback_list = feedback_list.filter(
                tanggal__date__gte=tgl_mulai
            )
        if tgl_akhir:
            feedback_list = feedback_list.filter(
                tanggal__date__lte=tgl_akhir
            )
    
    # Container for the 'Flowable' objects
    story = []
    
    # Add company header
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    normal_style = styles['Normal']
    
    # Set font sizes for title
    title_style.fontSize = 14
    title_style.fontName = 'Helvetica-Bold'
    title_style.alignment = 1  # Center alignment
    
    # Company name
    company_name = Paragraph("<b>PT VIQUAM KUPANG</b>", title_style)
    story.append(company_name)
    
    # Company address
    address_style = normal_style.clone('Address')
    address_style.fontSize = 9  # Set font size to 9pt
    address_style.alignment = 1  # Center alignment
    address = Paragraph("Jl. Cendrawasih, Lahilai Bissi Kopan, Kec. Kota Lama, Kota Kupang, Nusa Tenggara Timur", address_style)
    story.append(address)
    
    # Contact information
    contact_style = normal_style.clone('Contact')
    contact_style.fontSize = 9  # Set font size to 9pt
    contact_style.alignment = 1  # Center alignment
    contact = Paragraph("Telp: 2349076", contact_style)
    story.append(contact)
    
    # Date range if provided
    if date_range:
        date_paragraph = Paragraph(f"Periode: {date_range}", address_style)
        story.append(date_paragraph)
    
    # Add spacer between address/date and horizontal line
    story.append(Spacer(1, 12))
    
    # Double horizontal line (moved above table)
    # Using a 1x1 table for reliable horizontal line placement
    line_table = Table([['']], colWidths=[16*cm], rowHeights=[1])
    line_table.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (0, 0), 2, colors.black),  # Top line
        ('LINEBELOW', (0, 0), (0, 0), 1, colors.black),  # Bottom line
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 0),
        ('TOPPADDING', (0, 0), (0, 0), 0),
        ('BOTTOMPADDING', (0, 0), (0, 0), 0),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 12))
    
    # Add report title
    report_title_style = normal_style.clone('ReportTitle')
    report_title_style.fontSize = 12
    report_title_style.alignment = 1  # Center alignment
    report_title_style.fontName = 'Helvetica-Bold'
    report_title = Paragraph("LAPORAN FEEDBACK PELANGGAN", report_title_style)
    story.append(report_title)
    
    # Add filter information
    filter_info_style = normal_style.clone('FilterInfo')
    filter_info_style.fontSize = 9
    filter_info_style.alignment = 1  # Center alignment
    
    # Status filter info - Not applicable for this report, just show date range
    if date_range:
        date_filter_paragraph = Paragraph(f"Periode: {date_range}", filter_info_style)
        story.append(date_filter_paragraph)
    
    story.append(Spacer(1, 12))
    
    # Prepare data for table (without Rating column as requested)
    data = [['No.', 'Nama Pelanggan', 'Subjek', 'Tanggal']]
    
    for i, feedback in enumerate(feedback_list, 1):
        row = [
            str(i),
            feedback.idPelanggan.nama,
            feedback.isi[:30] + "..." if len(feedback.isi) > 30 else feedback.isi,
            feedback.tanggal.strftime("%d/%m/%Y")
        ]
        data.append(row)
    
    # Create table with improved styling
    table = Table(data, colWidths=[1.5*cm, 4*cm, 6*cm, 3*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    story.append(table)
    story.append(Spacer(1, 24))
    
    # Add signature section (positioned at bottom right)
    story.append(Spacer(1, 200))  # Push signature to bottom
    current_date = get_indonesian_date()
    signature_data = [
        ['', f'Kupang, {current_date}'],
        ['', 'Mengetahui,'],
        ['', 'Pimpinan PT Viquam Kupang'],
        ['', ''],
        ['', '(Alain N. Susanto)']
    ]
    
    signature_table = Table(signature_data, colWidths=[8*cm, 8*cm])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (1, -1), (1, -1), 30),
    ]))
    
    story.append(signature_table)
    
    # Build PDF
    doc.build(story)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response

def sopir_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        try:
            sopir = Sopir.objects.get(username=username)
            if sopir.check_password(password):
                # Store sopir info in session
                request.session['sopir_id'] = sopir.idSopir
                request.session['sopir_nama'] = sopir.nama
                messages.success(request, f'Selamat datang, {sopir.nama}!')
                return redirect('sopir-dashboard')
            else:
                messages.error(request, 'Password salah.')
        except Sopir.DoesNotExist:
            messages.error(request, 'Username tidak ditemukan.')
    
    return render(request, 'sopir/login.html')

def sopir_logout(request):
    # Clear session data
    if 'sopir_id' in request.session:
        del request.session['sopir_id']
    if 'sopir_nama' in request.session:
        del request.session['sopir_nama']
    
    messages.info(request, 'Anda telah logout.')
    return redirect('sopir-login')

def sopir_dashboard(request):
    # Perbaikan autentikasi: 100% session based
    if 'sopir_id' not in request.session and not request.user.is_superuser:
        messages.error(request, 'Silakan login terlebih dahulu.')
        return redirect('sopir-login')
    
    # Update logika: Wewenang baru sopir
    if request.user.is_superuser:
        # Superuser bisa mengakses semua pesanan dengan status 'Dikirim'
        pesanan_list = Pemesanan.objects.filter(
            status='Dikirim'
        ).select_related('idPelanggan', 'idSopir').order_by('-tanggalPemesanan')
            
        context = {
            'pesanan_list': pesanan_list,
            'user': request.user,
            'is_admin_view': True,  # Variabel kendali untuk template
            'pesanan_json': '[]',  # No map for admin view
        }
            
        return render(request, 'sopir/dashboard.html', context)
    
    # Get logged in sopir ID
    sopir_id = request.session['sopir_id']
        
    # Get orders assigned to this sopir with status 'Dikirim'
    pesanan_list = Pemesanan.objects.filter(
        status='Dikirim',
        idSopir_id=sopir_id
    ).select_related('idPelanggan', 'idSopir').order_by('-tanggalPemesanan')
    
    # Convert to list of dictionaries for Leaflet map
    pesanan_data = []
    for pesanan in pesanan_list:
        pesanan_data.append({
            'id': pesanan.idPemesanan,
            'pelanggan_nama': pesanan.idPelanggan.nama,
            'alamat': pesanan.alamatPengiriman,
            'lat': float(pesanan.latitude) if pesanan.latitude else None,
            'lng': float(pesanan.longitude) if pesanan.longitude else None,
            'total': str(pesanan.total),
        })
    
    import json
    pesanan_json = json.dumps(pesanan_data)
    
    context = {
        'pesanan_list': pesanan_list,
        'user': request.user,
        'is_admin_view': False,  # Variabel kendali untuk template (regular Sopir)
        'pesanan_json': pesanan_json,
    }
    
    return render(request, 'sopir/dashboard.html', context)

def sopir_edit_pengiriman(request, pk):
    # Perbaikan autentikasi: 100% session based
    if 'sopir_id' not in request.session and not request.user.is_superuser:
        messages.error(request, 'Silakan login terlebih dahulu.')
        return redirect('sopir-login')
    
    # Update logika: Wewenang baru sopir
    if request.user.is_superuser:
        # Superuser bisa mengakses semua pesanan dengan status 'Dikirim'
        try:
            pesanan = Pemesanan.objects.get(
                pk=pk,
                status='Dikirim'
            )
        except Pemesanan.DoesNotExist:
            messages.error(request, 'Pesanan tidak ditemukan.')
            return redirect('admin:core_pemesanan_changelist')
    else:
        # Sopir hanya bisa mengakses pesanan yang ditugaskan ke mereka
        sopir_id = request.session['sopir_id']
        try:
            pesanan = Pemesanan.objects.get(
                pk=pk,
                idSopir_id=sopir_id,
                status='Dikirim'
            )
        except Pemesanan.DoesNotExist:
            messages.error(request, 'Pesanan tidak ditemukan atau tidak memiliki akses.')
            return redirect('sopir-dashboard')
    
    if request.method == 'POST':
        form = SopirEditPengirimanForm(request.POST, request.FILES, instance=pesanan)
        if form.is_valid():
            # Validasi tambahan: Foto wajib untuk status 'Selesai'
            status_baru = form.cleaned_data['status']
            foto_pengiriman = request.FILES.get('fotoPengiriman')
            
            if status_baru == 'Selesai' and not foto_pengiriman and not pesanan.fotoPengiriman:
                messages.error(request, 'Foto bukti pengiriman wajib diunggah saat mengubah status menjadi Selesai.')
                return render(request, 'sopir/edit_pengiriman.html', {'form': form, 'pesanan': pesanan})
            
            # Simpan perubahan
            form.save()
            
            if status_baru == 'Selesai':
                messages.success(request, 'Pesanan berhasil diselesaikan dengan bukti foto.')
            elif status_baru == 'Dibatalkan':
                messages.success(request, 'Pesanan berhasil dibatalkan.')
            
            return redirect('sopir-dashboard')
    else:
        form = SopirEditPengirimanForm(instance=pesanan)
    
    context = {
        'form': form,
        'pesanan': pesanan,
        'user': request.user,
    }
    
    return render(request, 'sopir/edit_pengiriman.html', context)

def sopir_account(request):
    """
    Menampilkan informasi akun dan kendaraan.
    - Superuser: Melihat daftar semua sopir.
    - Sopir Biasa: Hanya melihat data profil dan kendaraan miliknya sendiri (Filter by PK).
    """
    
    # Perbaikan autentikasi: 100% session based
    if 'sopir_id' not in request.session and not request.user.is_superuser:
        messages.error(request, 'Silakan login terlebih dahulu.')
        return redirect('sopir-login')

    # --- LOGIKA UNTUK SUPERUSER (ADMIN) ---
    if request.user.is_superuser:
        sopir_list = Sopir.objects.all() # Admin diizinkan melihat semua
        context = {
            'sopir_list': sopir_list,
            'user': request.user,
            'is_admin_view': True,  # Variabel kendali untuk template
        }
        return render(request, 'sopir/sopir_account.html', context)

    # --- LOGIKA UNTUK SOPIR BIASA (STRICT PRIVACY) ---
    # Mengambil ID sopir dari session login portal sopir
    session_sopir_id = request.session.get('sopir_id')
    
    if not session_sopir_id:
        messages.error(request, 'Sesi berakhir, silakan login kembali.')
        return redirect('sopir-login')

    try:
        # Menggunakan filter 'pk' untuk memastikan data yang diambil sangat spesifik
        # pk merujuk pada Primary Key (idSopir) dari model Sopir
        sopir = Sopir.objects.get(pk=session_sopir_id)
        
        # Mengambil hanya kendaraan yang terkait dengan sopir ini saja
        kendaraan_list = Kendaraan.objects.filter(idSopir=sopir)

        # Context hanya berisi data individu, tidak mengirim 'sopir_list'
        context = {
            'sopir': sopir,
            'kendaraan_list': kendaraan_list,
            'user': request.user,
            'is_admin_view': False,  # Variabel kendali untuk template (regular Sopir)
        }
        
        return render(request, 'sopir/sopir_account.html', context)

    except Sopir.DoesNotExist:
        messages.error(request, 'Data akun Anda tidak ditemukan.')
        return redirect('sopir-dashboard')

# Utility functions for cart management
def get_keranjang(request):
    """Get cart from session or create empty cart"""
    keranjang = request.session.get('cart', {})
    return keranjang

def save_keranjang(request, keranjang):
    """Save cart to session"""
    request.session['cart'] = keranjang
    request.session.modified = True

# Pelanggan Views
def landing_page(request):
    """Landing page view"""
    # Check if user is logged in
    if 'pelanggan_id' in request.session:
        try:
            pelanggan_id = request.session['pelanggan_id']
            pelanggan = Pelanggan.objects.get(idPelanggan=pelanggan_id)
            # If logged in, redirect to home page
            return redirect('pelanggan_home')
        except Pelanggan.DoesNotExist:
            # If pelanggan doesn't exist, clear session
            del request.session['pelanggan_id']
            request.session.modified = True
    
    # For non-logged in users, show landing page
    return render(request, 'pelanggan/landing.html')

def pelanggan_register(request):
    """Register new pelanggan"""
    if request.method == 'POST':
        form = PelangganRegisterForm(request.POST)
        if form.is_valid():
            # Check if username already exists
            username = form.cleaned_data['username']
            if Pelanggan.objects.filter(username=username).exists():
                messages.error(request, 'Username sudah digunakan!')
                return render(request, 'pelanggan/register.html', {'form': form})
            
            # Save pelanggan
            pelanggan = form.save()
            messages.success(request, 'Registrasi berhasil! Silakan login.')
            return redirect('pelanggan_login')
    else:
        form = PelangganRegisterForm()
    
    return render(request, 'pelanggan/register.html', {'form': form})

def pelanggan_login(request):
    """Login pelanggan"""
    if request.method == 'POST':
        form = PelangganLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            
            try:
                pelanggan = Pelanggan.objects.get(username=username)
                
                if pelanggan.check_password(password):
                    # Simpan informasi pelanggan ke session dan pastikan session
                    # ditandai sebagai dimodifikasi agar backend menyimpannya segera.
                    request.session['pelanggan_id'] = pelanggan.idPelanggan
                    request.session['pelanggan_nama'] = pelanggan.nama
                    request.session['pelanggan_is_langganan'] = pelanggan.isLangganan
                    request.session.modified = True

                    messages.success(request, f'Selamat datang, {pelanggan.nama}!')
                    # NOTE: pastikan view `pelanggan_home` memeriksa
                    # `request.session.get('pelanggan_id')` untuk otorisasi akses.
                    return redirect('pelanggan_home')
                else:
                    messages.error(request, 'Password salah.')
            except Pelanggan.DoesNotExist:
                messages.error(request, 'Username tidak ditemukan.')
    else:
        form = PelangganLoginForm()
    
    return render(request, 'pelanggan/login.html', {'form': form})

def pelanggan_logout(request):
    """Logout pelanggan"""
    # Clear session data
    if 'pelanggan_id' in request.session:
        del request.session['pelanggan_id']
    if 'pelanggan_nama' in request.session:
        del request.session['pelanggan_nama']
    if 'pelanggan_is_langganan' in request.session:
        del request.session['pelanggan_is_langganan']
    if 'cart' in request.session:
        del request.session['cart']
    
    messages.info(request, 'Anda telah logout.')
    return redirect('landing')

def pelanggan_home(request):
    """Pelanggan home/dashboard after login.

    Memeriksa session kustom `pelanggan_id`. Jika tidak ada atau tidak valid,
    alihkan pengguna ke halaman login. Jika valid, render dashboard.
    """
    pelanggan_id = request.session.get('pelanggan_id')
    if not pelanggan_id:
        messages.info(request, 'Silakan login terlebih dahulu.')
        return redirect('pelanggan_login')

    try:
        pelanggan = Pelanggan.objects.get(idPelanggan=pelanggan_id)
    except Pelanggan.DoesNotExist:
        # Jika session berisi id yang tidak valid, bersihkan session
        request.session.pop('pelanggan_id', None)
        request.session.pop('pelanggan_nama', None)
        request.session.modified = True
        messages.error(request, 'Sesi pengguna tidak valid. Silakan login lagi.')
        return redirect('pelanggan_login')

    context = {
        'pelanggan': pelanggan,
    }

    return render(request, 'pelanggan/home.html', context)

@pelanggan_login_required
def list_produk(request):
    """List all available products"""
    # Get products with stock > 0
    produk_list = Produk.objects.filter(stok__gt=0).order_by('namaProduk')
    
    # Pagination
    paginator = Paginator(produk_list, 12)  # Show 12 products per page
    page_number = request.GET.get('page')
    produk_page = paginator.get_page(page_number)
    
    context = {
        'produk_list': produk_page,
    }
    
    return render(request, 'pelanggan/produk_list.html', context)

@pelanggan_login_required
def detail_produk(request, pk):
    """Show product detail"""
    try:
        produk = Produk.objects.get(idProduk=pk, stok__gt=0)
    except Produk.DoesNotExist:
        messages.error(request, 'Produk tidak ditemukan atau stok habis.')
        return redirect('list_produk')
    
    context = {
        'produk': produk,
    }
    
    return render(request, 'pelanggan/detail_produk.html', context)

@pelanggan_login_required
def tambah_ke_keranjang(request, pk):
    """Add product to cart"""
    if request.method == 'POST':
        try:
            produk = Produk.objects.get(idProduk=pk)
            if produk.stok <= 0:
                messages.error(request, 'Produk tidak ditemukan atau stok habis.')
                return redirect('list_produk')
        except Produk.DoesNotExist:
            messages.error(request, 'Produk tidak ditemukan.')
            return redirect('list_produk')
        
        # Get quantity from POST data
        try:
            quantity = int(request.POST.get('quantity', 1))
        except ValueError:
            quantity = 1
        
        # Validate quantity
        if quantity <= 0:
            messages.error(request, 'Jumlah harus lebih dari 0.')
            return redirect('list_produk')
        
        if quantity > produk.stok:
            messages.error(request, f'Stok tidak mencukupi. Stok tersedia: {produk.stok}')
            return redirect('list_produk')
        
        # Get cart from session
        keranjang = get_keranjang(request)
        
        # Add product to cart
        product_id = str(produk.idProduk)
        if product_id in keranjang:
            # Update quantity if product already in cart
            new_quantity = keranjang[product_id]['quantity'] + quantity
            # Check if total quantity exceeds stock
            if new_quantity > produk.stok:
                # Adjust quantity to maximum available
                new_quantity = produk.stok
                messages.warning(request, f'Jumlah di keranjang telah disesuaikan dengan stok tersedia: {produk.stok}')
            keranjang[product_id]['quantity'] = new_quantity
        else:
            # Add new product to cart
            keranjang[product_id] = {
                'nama': produk.namaProduk,
                'harga': float(produk.hargaPerDus),
                'quantity': quantity,
                'stok': produk.stok,
                'satuan': produk.satuan  # <--- Tambahkan baris ini
            }
        
        # Save cart to session
        save_keranjang(request, keranjang)
        
        messages.success(request, f'{quantity} {produk.satuan} {produk.namaProduk} berhasil ditambahkan ke keranjang!')
        return redirect('list_produk')
    
    return redirect('list_produk')

@pelanggan_login_required
def view_keranjang(request):
    """View cart contents"""
    # Get cart from session
    keranjang = get_keranjang(request)
    
    # Calculate totals
    total_items = 0
    total_price = 0
    cart_items = []
    
    for product_id, item in keranjang.items():
        subtotal = item['harga'] * item['quantity']
        total_items += item['quantity']
        total_price += subtotal
        
        cart_items.append({
            'id': product_id,
            'nama': item['nama'],
            'harga': item['harga'],
            'quantity': item['quantity'],
            'subtotal': subtotal,
            'stok': item['stok'],
            'satuan': item.get('satuan', 'Dus')  # <--- Tambahkan baris ini
        })
    
    context = {
        'cart_items': cart_items,
        'total_items': total_items,
        'total_price': total_price,
    }
    
    return render(request, 'pelanggan/keranjang.html', context)

@pelanggan_login_required
def update_keranjang(request, pk):
    """Update item quantity in cart"""
    if request.method == 'POST':
        try:
            produk = Produk.objects.get(idProduk=pk)
        except Produk.DoesNotExist:
            messages.error(request, 'Produk tidak ditemukan.')
            return redirect('view_keranjang')
        
        # Get new quantity from POST data
        try:
            quantity = int(request.POST.get('quantity', 1))
        except ValueError:
            quantity = 1
        
        # Validate quantity
        if quantity <= 0:
            return remove_from_keranjang(request, pk)
        
        if quantity > produk.stok:
            messages.error(request, f'Stok tidak mencukupi. Stok tersedia: {produk.stok}')
            quantity = produk.stok
        
        # Get cart from session
        keranjang = get_keranjang(request)
        
        # Update quantity
        product_id = str(produk.idProduk)
        if product_id in keranjang:
            keranjang[product_id]['quantity'] = quantity
            save_keranjang(request, keranjang)
            messages.success(request, f'Jumlah {produk.namaProduk} telah diperbarui.')
        else:
            messages.error(request, 'Produk tidak ditemukan di keranjang.')
    
    return redirect('view_keranjang')

@pelanggan_login_required
def remove_from_keranjang(request, pk):
    """Remove item from cart"""
    # Get cart from session
    keranjang = get_keranjang(request)
    
    # Remove item
    product_id = str(pk)
    if product_id in keranjang:
        nama_produk = keranjang[product_id]['nama']
        del keranjang[product_id]
        save_keranjang(request, keranjang)
        messages.success(request, f'{nama_produk} telah dihapus dari keranjang.')
    else:
        messages.error(request, 'Produk tidak ditemukan di keranjang.')
    
    return redirect('view_keranjang')

@pelanggan_login_required
def checkout_pemesanan(request):
    """Checkout process with transaction safety"""
    # Get pelanggan early for context
    pelanggan_id = request.session['pelanggan_id']
    pelanggan = Pelanggan.objects.get(idPelanggan=pelanggan_id)
    
    # Get cart from session
    keranjang = get_keranjang(request)
    
    # Check if cart is empty
    if not keranjang:
        messages.error(request, 'Keranjang belanja kosong.')
        return redirect('view_keranjang')
    
    # Calculate totals using Decimal for consistency
    from decimal import Decimal
    total_items = 0
    total_price = Decimal('0.00')
    cart_items = []
    
    for product_id, item in keranjang.items():
        # Convert to Decimal for safe calculation
        harga_item = Decimal(str(item['harga']))
        quantity_item = Decimal(str(item['quantity']))
        subtotal = harga_item * quantity_item
        total_items += item['quantity']
        total_price += subtotal
        
        cart_items.append({
            'id': product_id,
            'nama': item['nama'],
            'harga': float(harga_item),
            'quantity': item['quantity'],
            'subtotal': float(subtotal),
            'stok': item['stok'],
            'satuan': item.get('satuan', 'Dus')
        })
    
    if request.method == 'POST':
        # Get pelanggan from session to determine customer type
        pelanggan_id = request.session['pelanggan_id']
        pelanggan = Pelanggan.objects.get(idPelanggan=pelanggan_id)
        
        # Initialize form with is_langganan parameter
        form = PemesananCheckoutForm(request.POST, request.FILES, is_langganan=pelanggan.isLangganan)
        
        if form.is_valid():
            # Determine bukti bayar requirement based on customer type and payment method
            bukti_bayar = request.FILES.get('buktiBayar')
            jenis_pembayaran = form.cleaned_data.get('jenisPembayaran', 'Transfer')
            
            # Validasi bukti bayar berdasarkan tipe pelanggan dan metode pembayaran
            if pelanggan.isLangganan:
                # Pelanggan langganan
                if jenis_pembayaran == 'Transfer' and not bukti_bayar:
                    messages.error(request, 'Bukti pembayaran wajib diunggah untuk Transfer.')
                    return render(request, 'pelanggan/checkout.html', {
                        'form': form,
                        'cart_items': cart_items,
                        'total_items': total_items,
                        'total_price': total_price,
                        'is_langganan': pelanggan.isLangganan,
                    })
            else:
                # Pelanggan umum - WAJIB bukti bayar
                if not bukti_bayar:
                    messages.error(request, 'Bukti pembayaran wajib diunggah.')
                    return render(request, 'pelanggan/checkout.html', {
                        'form': form,
                        'cart_items': cart_items,
                        'total_items': total_items,
                        'total_price': total_price,
                        'is_langganan': pelanggan.isLangganan,
                    })
            
            # Use atomic transaction to ensure data consistency
            with transaction.atomic():
                # Create new pemesanan with latitude and longitude
                latitude = form.cleaned_data.get('latitude')
                longitude = form.cleaned_data.get('longitude')
                
                # Determine payment fields based on customer type
                if pelanggan.isLangganan:
                    # Pelanggan langganan - use form data
                    jenis_pembayaran = form.cleaned_data['jenisPembayaran']
                    
                    # Calculate status pembayaran and sisa tagihan based on payment method
                    if jenis_pembayaran == 'Transfer':
                        status_pembayaran = 'Lunas'
                        nominal_dibayar = total_price
                        sisa_tagihan = Decimal('0.00')
                        jatuh_tempo = None
                    elif jenis_pembayaran == 'COD':
                        status_pembayaran = 'Belum Bayar'
                        nominal_dibayar = Decimal('0.00')
                        sisa_tagihan = total_price
                        jatuh_tempo = None
                    elif jenis_pembayaran == 'Piutang':
                        status_pembayaran = 'Belum Bayar'
                        nominal_dibayar = Decimal('0.00')
                        sisa_tagihan = total_price
                        jatuh_tempo = None  # Will be set by admin later
                else:
                    # Pelanggan umum - default to Transfer/Lunas
                    jenis_pembayaran = 'Transfer'
                    status_pembayaran = 'Lunas'
                    nominal_dibayar = total_price
                    sisa_tagihan = Decimal('0.00')
                    jatuh_tempo = None
                
                pemesanan = Pemesanan.objects.create(
                    idPelanggan=pelanggan,
                    latitude=latitude,
                    longitude=longitude,
                    alamatPengiriman=form.cleaned_data['alamatPengiriman'],
                    total=total_price,
                    buktiBayar=bukti_bayar if bukti_bayar else None,
                    status='Diproses',
                    jenisPembayaran=jenis_pembayaran,
                    statusPembayaran=status_pembayaran,
                    nominalDibayar=nominal_dibayar,
                    sisaTagihan=sisa_tagihan,
                    jatuhTempo=jatuh_tempo
                )
                
                # Create detail pemesanan for each item in cart
                for item in cart_items:
                    # Get produk
                    produk = Produk.objects.get(idProduk=item['id'])
                    
                    # Check stock availability
                    if item['quantity'] > produk.stok:
                        raise ValueError(f'Stok {produk.namaProduk} tidak mencukupi.')
                    
                    # Create detail pemesanan
                    DetailPemesanan.objects.create(
                        idPemesanan=pemesanan,
                        idProduk=produk,
                        jumlah=item['quantity'],
                        subTotal=item['subtotal']
                    )
                
                # Clear cart from session
                del request.session['cart']
                request.session.modified = True
                
                messages.success(request, 'Pesanan berhasil dibuat!')
                return redirect('riwayat_pesanan')
        else:
            # Format form errors into user-friendly messages
            error_messages = []
            for field, errors in form.errors.items():
                for error in errors:
                    if field == 'buktiBayar':
                        error_messages.append('Bukti pembayaran wajib diupload.')
                    elif field == 'jenisPembayaran':
                        error_messages.append(error)
                    elif field == 'nominalDibayar':
                        error_messages.append(error)
                    elif field == 'jatuhTempo':
                        error_messages.append(error)
                    else:
                        error_messages.append(error)
            
            # Remove duplicates and join
            error_messages = list(dict.fromkeys(error_messages))
            messages.error(request, ' '.join(error_messages))
    else:
        # Pre-fill address with pelanggan's address
        pelanggan_id = request.session['pelanggan_id']
        pelanggan = Pelanggan.objects.get(idPelanggan=pelanggan_id)
        initial_data = {'alamatPengiriman': pelanggan.alamat}
        
        # Pass is_langganan to form
        form = PemesananCheckoutForm(initial=initial_data, is_langganan=pelanggan.isLangganan)
    
    context = {
        'form': form,
        'cart_items': cart_items,
        'total_items': total_items,
        'total_price': total_price,
        'is_langganan': pelanggan.isLangganan,  # Context untuk template checkout
    }
    
    return render(request, 'pelanggan/checkout.html', context)

@pelanggan_login_required
def riwayat_pesanan(request):
    """View order history"""
    # Get pelanggan from session
    pelanggan_id = request.session['pelanggan_id']
    pelanggan = Pelanggan.objects.get(idPelanggan=pelanggan_id)
    
    # Get all orders for this pelanggan
    pesanan_list = Pemesanan.objects.filter(idPelanggan=pelanggan).order_by('-tanggalPemesanan')
    
    context = {
        'pesanan_list': pesanan_list,
    }
    
    return render(request, 'pelanggan/riwayat_pesanan.html', context)

@pelanggan_login_required
def detail_pesanan(request, pk):
    """View order detail"""
    # Get pelanggan from session
    pelanggan_id = request.session['pelanggan_id']
    pelanggan = Pelanggan.objects.get(idPelanggan=pelanggan_id)
    
    try:
        # Get order that belongs to this pelanggan
        pesanan = Pemesanan.objects.get(idPemesanan=pk, idPelanggan=pelanggan)
    except Pemesanan.DoesNotExist:
        messages.error(request, 'Pesanan tidak ditemukan.')
        return redirect('riwayat_pesanan')
    
    # Get all orders for this pelanggan to determine order number
    all_orders = Pemesanan.objects.filter(idPelanggan=pelanggan).order_by('-tanggalPemesanan')
    order_number = None
    for i, order in enumerate(all_orders, 1):
        if order.idPemesanan == pesanan.idPemesanan:
            order_number = i
            break
    
    # Get order details
    detail_list = DetailPemesanan.objects.filter(idPemesanan=pesanan)
    
    context = {
        'pesanan': pesanan,
        'detail_list': detail_list,
        'order_number': order_number,
    }
    
    return render(request, 'pelanggan/detail_pesanan.html', context)

@pelanggan_login_required
def pelanggan_account(request):
    """View and update pelanggan account"""
    # Get pelanggan from session
    pelanggan_id = request.session['pelanggan_id']
    pelanggan = Pelanggan.objects.get(idPelanggan=pelanggan_id)
    
    if request.method == 'POST':
        if 'update_profile' in request.POST:
            # Update profile
            form = PelangganUpdateForm(request.POST, instance=pelanggan)
            if form.is_valid():
                form.save()
                messages.success(request, 'Profil berhasil diperbarui.')
                return redirect('pelanggan_account')
            else:
                messages.error(request, 'Terjadi kesalahan pada form.')
        elif 'change_password' in request.POST:
            # Change password
            form = ChangePasswordForm(pelanggan, request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, 'Password berhasil diubah.')
                return redirect('pelanggan_account')
            else:
                messages.error(request, 'Terjadi kesalahan pada form.')
    else:
        form = PelangganUpdateForm(instance=pelanggan)
        password_form = ChangePasswordForm(pelanggan)
    
    context = {
        'pelanggan': pelanggan,
        'form': form,
        'password_form': ChangePasswordForm(pelanggan),
    }
    
    return render(request, 'pelanggan/akun.html', context)


@pelanggan_login_required
def batal_pesanan(request, pk):
    """Cancel an order if status is 'Diproses'"""
    # Get pelanggan from session
    pelanggan_id = request.session['pelanggan_id']
    pelanggan = Pelanggan.objects.get(idPelanggan=pelanggan_id)
    
    try:
        # Get order that belongs to this pelanggan
        pesanan = Pemesanan.objects.get(idPemesanan=pk, idPelanggan=pelanggan)
    except Pemesanan.DoesNotExist:
        messages.error(request, 'Pesanan tidak ditemukan.')
        return redirect('riwayat_pesanan')
    
    # Check if order can be cancelled
    if pesanan.status != 'Diproses':
        messages.error(request, 'Pesanan tidak dapat dibatalkan karena sudah diproses atau selesai.')
        return redirect('riwayat_pesanan')
    
    # Cancel the order
    pesanan.status = 'Dibatalkan'
    pesanan.save()
    
    messages.success(request, 'Pesanan berhasil dibatalkan. Stok telah dikembalikan.')
    return redirect('riwayat_pesanan')


def kirim_feedback(request):
    """Submit feedback from customer"""
    # Check if user is logged in
    if 'pelanggan_id' not in request.session:
        messages.error(request, 'Anda harus login untuk memberikan feedback.')
        return redirect('landing')
    
    try:
        pelanggan_id = request.session['pelanggan_id']
        pelanggan = Pelanggan.objects.get(idPelanggan=pelanggan_id)
    except Pelanggan.DoesNotExist:
        # If pelanggan doesn't exist, clear session
        del request.session['pelanggan_id']
        request.session.modified = True
        messages.error(request, 'Sesi tidak valid. Silakan login kembali.')
        return redirect('landing')
    
    if request.method == 'POST':
        feedback_text = request.POST.get('feedback', '').strip()
        if feedback_text:
            # Create feedback
            Feedback.objects.create(
                idPelanggan=pelanggan,
                isi=feedback_text
            )
            messages.success(request, 'Terima kasih atas feedback Anda!')
        else:
            messages.error(request, 'Feedback tidak boleh kosong.')
        
        # Redirect back to landing page
        return redirect('landing')
    
    # If not POST request, redirect to landing page
    return redirect('landing')


# Feedback submission and landing page redirection handled here
