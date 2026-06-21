from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

# 1. KONFIGURASI DATABASE, SECURITY, & UPLOAD FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/db_akademik'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'kuncirahasiaku123' 

# Konfigurasi Upload Foto
UPLOAD_FOLDER = 'static/uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Pastikan folder static/uploads sudah terbuat otomatis jika belum ada
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db = SQLAlchemy(app)

# Fungsi untuk cek format file
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ================= 2. STRUKTUR TABEL (MODELS) =================

class Mahasiswa(db.Model):
    __tablename__ = 'mahasiswa'
    nim = db.Column(db.String(10), primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    jurusan = db.Column(db.String(100), nullable=False)
    foto = db.Column(db.String(255), nullable=True) # Menyimpan nama file foto

class Matakuliah(db.Model):
    __tablename__ = 'matakuliah'
    kode_mk = db.Column(db.String(10), primary_key=True)
    nama_mk = db.Column(db.String(100), nullable=False)
    sks = db.Column(db.Integer, nullable=False)

class KRS(db.Model):
    __tablename__ = 'krs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nim_mahasiswa = db.Column(db.String(10), db.ForeignKey('mahasiswa.nim'), nullable=False)
    kode_matakuliah = db.Column(db.String(10), db.ForeignKey('matakuliah.kode_mk'), nullable=False)

    mahasiswa = db.relationship('Mahasiswa', backref=db.backref('krs_list', lazy=True))
    matakuliah = db.relationship('Matakuliah', backref=db.backref('krs_list', lazy=True))


# ================= 3. ROUTE CRUD MAHASISWA =================

@app.route('/')
def index():
    return redirect(url_for('mahasiswa_index'))

@app.route('/mahasiswa')
def mahasiswa_index():
    semua_mhs = Mahasiswa.query.all()
    return render_template('mahasiswa.html', data_mahasiswa=semua_mhs)

@app.route('/mahasiswa/tambah', methods=['POST'])
def mahasiswa_tambah():
    nim = request.form.get('nim')
    nama = request.form.get('nama')
    jurusan = request.form.get('jurusan')
    
    mahasiswa_exist = Mahasiswa.query.get(nim)
    if mahasiswa_exist:
        flash(f'Gagal menambah data! NIM {nim} sudah terdaftar atas nama {mahasiswa_exist.nama}.', 'danger')
        return redirect(url_for('mahasiswa_index'))

    # Proses Upload File Foto
    filename = None
    if 'foto' in request.files:
        file = request.files['foto']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Beri nama unik pakai NIM biar tidak bentrok antar mahasiswa
            filename = f"{nim}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    
    mhs_baru = Mahasiswa(nim=nim, nama=nama, jurusan=jurusan, foto=filename)
    db.session.add(mhs_baru)
    db.session.commit()
    flash(f'Data Mahasiswa {nama} berhasil ditambahkan.', 'success')
    return redirect(url_for('mahasiswa_index'))

@app.route('/mahasiswa/edit/<string:nim>', methods=['GET', 'POST'])
def mahasiswa_edit(nim):
    mhs_lama = Mahasiswa.query.get_or_404(nim)
    
    if request.method == 'POST':
        nim_baru = request.form.get('nim')
        nama_baru = request.form.get('nama')
        jurusan_baru = request.form.get('jurusan')
        
        # Cek apakah ada file foto baru yang di-upload
        filename = mhs_lama.foto # Default pakai foto lama
        if 'foto' in request.files:
            file = request.files['foto']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filename = f"{nim_baru}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        if nim_baru != nim:
            mhs_lain = Mahasiswa.query.get(nim_baru)
            if mhs_lain:
                flash(f'Gagal mengubah data! NIM {nim_baru} sudah digunakan oleh mahasiswa bernama {mhs_lain.nama}.', 'danger')
                return redirect(url_for('mahasiswa_index'))
            
            try:
                krs_lama = KRS.query.filter_by(nim_mahasiswa=nim).all()
                mhs_baru = Mahasiswa(nim=nim_baru, nama=nama_baru, jurusan=jurusan_baru, foto=filename)
                db.session.add(mhs_baru)
                db.session.flush()
                
                for krs in krs_lama:
                    krs.nim_mahasiswa = nim_baru
                
                db.session.delete(mhs_lama)
                db.session.commit()
                flash(f'Data Mahasiswa berhasil diperbarui dengan NIM baru {nim_baru}.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Terjadi kesalahan sistem saat ganti NIM!', 'danger')
        else:
            mhs_lama.nama = nama_baru
            mhs_lama.jurusan = jurusan_baru
            mhs_lama.foto = filename
            db.session.commit()
            flash(f'Data Mahasiswa {mhs_lama.nama} berhasil diperbarui.', 'success')
            
        return redirect(url_for('mahasiswa_index'))
        
    return render_template('edit_mahasiswa.html', mhs=mhs_lama)

@app.route('/mahasiswa/hapus/<string:nim>')
def mahasiswa_hapus(nim):
    mhs = Mahasiswa.query.get_or_404(nim)
    krs_terkait = KRS.query.filter_by(nim_mahasiswa=nim).first()
    
    if krs_terkait:
        flash(f'Data Mahasiswa {mhs.nama} ({mhs.nim}) GAGAL dihapus karena masih mengambil KRS!', 'danger')
    else:
        # Hapus file fisik fotonya juga di folder uploads jika ada
        if mhs.foto:
            foto_path = os.path.join(app.config['UPLOAD_FOLDER'], mhs.foto)
            if os.path.exists(foto_path):
                os.remove(foto_path)
                
        db.session.delete(mhs)
        db.session.commit()
        flash(f'Data Mahasiswa {mhs.nama} berhasil dihapus.', 'success')
        
    return redirect(url_for('mahasiswa_index'))

@app.route('/mahasiswa/cetak/<string:nim>')
def mahasiswa_cetak(nim):
    mhs = Mahasiswa.query.get_or_404(nim)
    return render_template('cetak_ktm.html', mhs=mhs)

# ================= ROUTE CRUD MATAKULIAH & KRS (SAMA SEPERTI SEBELUMNYA) =================
@app.route('/matakuliah')
def matakuliah_index():
    semua_mk = Matakuliah.query.all()
    return render_template('matakuliah.html', data_matakuliah=semua_mk)

@app.route('/matakuliah/tambah', methods=['POST'])
def matakuliah_tambah():
    kode_mk = request.form.get('kode_mk')
    nama_mk = request.form.get('nama_mk')
    sks = request.form.get('sks')
    mk_exist = Matakuliah.query.get(kode_mk)
    if mk_exist:
        flash(f'Gagal menambah data! Kode MK {kode_mk} sudah digunakan oleh "{mk_exist.nama_mk}".', 'danger')
    else:
        mk_baru = Matakuliah(kode_mk=kode_mk, nama_mk=nama_mk, sks=sks)
        db.session.add(mk_baru)
        db.session.commit()
        flash(f'Matakuliah {nama_mk} berhasil ditambahkan.', 'success')
    return redirect(url_for('matakuliah_index'))

@app.route('/matakuliah/edit/<string:kode_mk>', methods=['GET', 'POST'])
def matakuliah_edit(kode_mk):
    mk = Matakuliah.query.get_or_404(kode_mk)
    if request.method == 'POST':
        mk.nama_mk = request.form.get('nama_mk')
        mk.sks = request.form.get('sks')
        db.session.commit()
        flash(f'Matakuliah {mk.nama_mk} berhasil diperbarui.', 'success')
        return redirect(url_for('matakuliah_index'))
    return render_template('edit_matakuliah.html', mk=mk)

@app.route('/matakuliah/hapus/<string:kode_mk>')
def matakuliah_hapus(kode_mk):
    mk = Matakuliah.query.get_or_404(kode_mk)
    krs_terkait = KRS.query.filter_by(kode_matakuliah=kode_mk).first()
    if krs_terkait:
        flash(f'Matakuliah {mk.nama_mk} GAGAL dihapus karena sedang diambil mahasiswa di KRS!', 'danger')
    else:
        db.session.delete(mk)
        db.session.commit()
        flash(f'Matakuliah {mk.nama_mk} berhasil dihapus.', 'success')
    return redirect(url_for('matakuliah_index'))

@app.route('/krs')
def krs_index():
    semua_krs = KRS.query.all()
    semua_mhs = Mahasiswa.query.all()
    semua_mk = Matakuliah.query.all()
    return render_template('krs.html', data_krs=semua_krs, data_mahasiswa=semua_mhs, data_matakuliah=semua_mk)

@app.route('/krs/tambah', methods=['POST'])
def krs_tambah():
    krs_baru = KRS(nim_mahasiswa=request.form.get('nim_mahasiswa'), kode_matakuliah=request.form.get('kode_matakuliah'))
    db.session.add(krs_baru)
    db.session.commit()
    flash('KRS Mahasiswa berhasil disimpan.', 'success')
    return redirect(url_for('krs_index'))

@app.route('/krs/hapus/<int:id>')
def krs_hapus(id):
    krs = KRS.query.get_or_404(id)
    db.session.delete(krs)
    db.session.commit()
    flash('Data KRS berhasil dibatalkan.', 'success')
    return redirect(url_for('krs_index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  
    app.run(debug=True)