import sys,bioread,numpy as np
from scipy.signal import butter,filtfilt,find_peaks,welch
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import pyqtgraph as pg

pg.setConfigOptions(antialias=False,useOpenGL=True)

FS=1000 #Frecuencia de Muestreo
VENTANA_EEG=10 #Segundos que se utilizan para EEG
VENTANA_RMSSD=60 #Segundos que se utilizan para RMSSD
UPDATE_MS=200 #Tiempo entre cada actualización 0.2 segundos

#Elimina las frecuencias no útiles
def bandpass(signal,low,high,fs,order=4): #Filtro de orden 4, filtra de forma equilibrada
    nyq=fs/2 #Frecuencia Nyquist
    b,a=butter(order,[low/nyq,high/nyq],btype="band") #Genera coeficientes del numerador (b) y denominador (a)
    return filtfilt(b,a,signal) #Filtra hacia adelante y atrás lo que no desplaza la señal

#Obtiene la potencia alpha
def alpha_power(segmento):
    eeg=bandpass(segmento,1,40,FS) #Filtra y se conserva de 1 a 40 Hz
    freqs,psd=welch(eeg,fs=FS,nperseg=min(4096,len(eeg))) #Welch calcula la "Power Spectral Density" lo cual nos dice cuánta energía hay por frecuencia
    mask=(freqs>=8)&(freqs<=13) #Selecciona la Banda Alpha la cual tiene un rango de 8 a 13 Hz
    return float(np.trapezoid(psd[mask],freqs[mask])) #Integra el área lo que nos da nuestra Potencia alpha

#Mide la variabilidad cardiaca
def calcular_rmssd(segmento):
    ecg=bandpass(segmento,5,25,FS) #Mantiene nuestro complejo QRS
    peaks,_=find_peaks(ecg,distance=0.5*FS,prominence=np.std(ecg)) #Encuentra los picos de R y no permiten que sean >120 BPM
    if len(peaks)<3:return np.nan,0
    rr=np.diff(peaks)/FS #Convierte las muestras a segundos
    return np.sqrt(np.mean(np.diff(rr)**2))*1000,60/np.mean(rr) #Se determina el bpm

def calcular_lfhf(ecg):

    peaks, _ = find_peaks(
        ecg,
        distance=FS*0.4, #Distancia minima de 0.4 segundos lo cual equivale a  distance=FS*0.4
        prominence=np.std(ecg)*0.5 #Ignora el ruido pequeño, mas alto significa menos picos, mas bajos mas falsos
    )

    # Debe haber suficientes picos
    if len(peaks) < 4:
        return 0,0,0

    rr = np.diff(peaks) / FS #Hace el calculo de RR = t2 - t1

    # Tiempo asociado a cada intervalo RR
    t = peaks[1:] / FS

    # Seguridad extra
    if len(rr) != len(t):
        return 0,0,0

    fs_interp = 4 #Reconstruye RR a 4 Hz el cual es un estandar HRV

    t_uniform = np.arange(
        t[0],
        t[-1],
        1/fs_interp
    )

    if len(t_uniform) < 4:
        return 0,0,0

#Convierte datos irregulares a datos uniformes, esto debido a que Welch necesita muestras uniformes
    rr_interp = np.interp(
        t_uniform,
        t,
        rr
    )

    f, pxx = welch(
        rr_interp,
        fs=fs_interp,
        nperseg=min(256, len(rr_interp)) #La cantidad de datos que utiliza welch, cuantos mas son mayor resolucion habra y cuantos menos mas estabilidad
    )

#Es el area bajo la curva (Integral de PSD), cuanto mas area habra mas actividad
    lf = np.trapz( 
        pxx[(f>=0.04)&(f<0.15)],
        f[(f>=0.04)&(f<0.15)]
    )

    hf = np.trapz(
        pxx[(f>=0.15)&(f<0.40)],
        f[(f>=0.15)&(f<0.40)]
    )

    lfhf = lf/(hf+1e-6)

    return lf,hf,lfhf

#Se obtiene nuestra referencia "Estandar de Oro"
def calibrar(path):

    data=bioread.read_file(path)

    eeg=data.channels[0].data
    ecg=data.channels[1].data

    alpha = alpha_power(eeg)

    rmssd,_ = calcular_rmssd(ecg)

    _,_,lfhf = calcular_lfhf(ecg)

    if np.isnan(lfhf) or lfhf <= 0:
        lfhf = 1

    return alpha,rmssd,lfhf

#Toda la interfaz
class SemaforoGUI(QWidget):

#Guarda eeg y ecg
    def __init__(self,eeg,ecg,alpha_basal,rmssd_basal,lfhf_basal):
        super().__init__() #Inicializa QWidget

        self.eeg=eeg
        self.ecg=ecg

        self.alpha_basal=alpha_basal
        self.rmssd_basal=rmssd_basal
        self.lfhf_basal=lfhf_basal

#Posición actual
        self.ptr=0
#Tiempo (Inicia en 0)
        self.segundos=0

#Historial para suavizar
        self.hist_alpha=[]
#Evita recalcular Alpha
        self.alpha_cache=0

        self.init_ui()

#Cada UPDATE_MS se ejecuta update_data()
        self.timer=QTimer() #Reloj interno
        self.timer.timeout.connect(self.update_data)
        self.timer.start(UPDATE_MS)

#Reanuda las graficas
    def iniciar(self):
        if not self.timer.isActive():
            self.timer.start(UPDATE_MS)

#Pausa las graficas
    def pausar(self):
        self.timer.stop()

#Construye el semaforo, texto, graficas y los indicadores
    def init_ui(self):

        self.setWindowTitle("Proyecto A — Biofeedback")
        self.setStyleSheet("QWidget{background:black;color:white;}")

        main=QVBoxLayout()

        self.semaforo=QLabel()
        self.semaforo.setFixedSize(250,250)
        self.semaforo.setStyleSheet(
            "background:red;border-radius:125px;"
        )

        self.estado=QLabel("CALIBRANDO")
        self.estado.setAlignment(Qt.AlignCenter)
        self.estado.setStyleSheet(
            "font-size:48px;font-weight:bold;"
        )

        main.addWidget(
            self.semaforo,
            alignment=Qt.AlignCenter
        )

        main.addWidget(
            self.estado
        )

        botones=QHBoxLayout()

        self.btn_inicio=QPushButton("INICIAR")
        self.btn_pausa=QPushButton("PAUSA")

        for b in [self.btn_inicio,self.btn_pausa]:

            b.setFixedHeight(55)

            b.setStyleSheet("""
                QPushButton{
                    background:#222;
                    color:white;
                    font-size:22px;
                    border:2px solid white;
                }
                QPushButton:hover{
                    background:#333;
                }
            """)

            botones.addWidget(b)

        self.btn_inicio.clicked.connect(self.iniciar)
        self.btn_pausa.clicked.connect(self.pausar)

        main.addLayout(botones)

        graficas=QHBoxLayout()

        self.plot_ecg=pg.PlotWidget()
        self.plot_eeg=pg.PlotWidget()

        self.plot_ecg.setLabel(
            "bottom",
            "Tiempo",
            "s"
        )

        self.plot_ecg.setLabel(
            "left",
            "Amplitud",
            "mV"
        )

        self.plot_eeg.setLabel(
          "bottom",
         "Tiempo",
          "s"
        )

        self.plot_eeg.setLabel(
         "left",
         "Amplitud",
        "µV"
    )

        for p in [self.plot_ecg,self.plot_eeg]:

            p.setBackground("black")

            p.showGrid(
                True,
                True
            )

            p.setMinimumHeight(
                180
            )

            p.disableAutoRange()

        self.curve_ecg=self.plot_ecg.plot(pen="w")
        self.curve_eeg=self.plot_eeg.plot(pen="w")

        graficas.addWidget(
            self.plot_ecg
        )

        graficas.addWidget(
            self.plot_eeg
        )

        main.addLayout(
            graficas
        )

        self.lbl_tiempo=QLabel()
        self.lbl_bpm=QLabel()
        self.lbl_alpha=QLabel()
        self.lbl_rmssd=QLabel()
        self.lbl_score=QLabel()
        self.lbl_lf=QLabel()
        self.lbl_hf=QLabel()
        self.lbl_lfhf=QLabel()

        datos=QGridLayout()

        labels=[
        self.lbl_tiempo,
        self.lbl_bpm,
        self.lbl_alpha,
        self.lbl_rmssd,
        self.lbl_score,
        self.lbl_lf,
        self.lbl_hf,
        self.lbl_lfhf
        ]

        for l in labels:
            l.setAlignment(Qt.AlignCenter)
            l.setStyleSheet("font-size:28px;")

        datos.addWidget(self.lbl_tiempo,0,0)
        datos.addWidget(self.lbl_bpm,0,1)
        datos.addWidget(self.lbl_alpha,0,2)
        datos.addWidget(self.lbl_rmssd,0,3)
        datos.addWidget(self.lbl_score,1,0)
        datos.addWidget(self.lbl_lf,1,1)
        datos.addWidget(self.lbl_hf,1,2)
        datos.addWidget(self.lbl_lfhf,1,3)

        for i in range(4):
            datos.setColumnStretch(i,1)

        datos.setVerticalSpacing(10)

        main.addLayout(datos)

        self.setLayout(main)

        self.resize(
            1800,
            900
        )

    def update_data(self):

#Ahora se actualiza cada 0.2 segundos
        self.segundos+=UPDATE_MS/1000
#Convierte segundos a muestras
        self.ptr=int(self.segundos*FS)

        if self.ptr>=len(self.eeg):
            self.timer.stop()
            return

        mins=int(self.segundos//60)
        secs=int(self.segundos%60)

        eeg_ini=max(
            0,
            int((self.segundos-VENTANA_EEG)*FS)
        )

        ecg_ini=max(
            0,
            int((self.segundos-VENTANA_RMSSD)*FS)
        )

#Ventanas eeg y ecg
        eeg_seg=self.eeg[eeg_ini:self.ptr]
        ecg_seg=self.ecg[ecg_ini:self.ptr]

#Se realiza el calculo de alpha cada 0.5 segundos
        if self.ptr%(FS//2)==0:
            self.alpha_cache=alpha_power(eeg_seg)

        alpha=self.alpha_cache

        rmssd,bpm=calcular_rmssd(ecg_seg)
        lf,hf,lfhf=calcular_lfhf(ecg_seg)

        print(
        "RR:",len(ecg_seg),
        "LF:",lf,
        "HF:",hf,
        "LFHF:",lfhf
        )

        if np.isnan(lf):lf=0
        if np.isnan(hf):hf=0
        if np.isnan(lfhf):lfhf=0

        if np.isnan(rmssd):
            rmssd=self.rmssd_basal

#Realiza una normalizacion, ejemplo: basal = 100, actual = 80 pasa a 0.8
        ratio=alpha/self.alpha_basal

        self.hist_alpha.append(ratio)

        if len(self.hist_alpha)>10:
            self.hist_alpha.pop(0)

        alpha_s=np.mean(self.hist_alpha)

#Estado relajado, alpha_s determina el color del semaforo 
        if alpha_s>=0.80 and lfhf < (self.lfhf_basal * 0.8):
            estado,color="RELAJADO","#00FF66"

#Estado estresado
        elif alpha_s<0.50 or rmssd < (self.rmssd_basal * 0.7) or lfhf > (self.lfhf_basal * 1.3):
            estado,color="ESTRÉS","#FF2222"

#Estado de alerta
        else:
            estado,color="INTERMEDIO","#FFD700"

        self.estado.setText(estado)
        self.estado.setStyleSheet(f"font-size:48px;color:{color};font-weight:bold;")
#Cambio visual del semaforo
        self.semaforo.setStyleSheet(f"background:{color};border-radius:125px;")
        self.lbl_tiempo.setText(f"TIEMPO: {mins:02}:{secs:02}")
        self.lbl_bpm.setText(f"BPM: {int(bpm)}")
        self.lbl_alpha.setText(f"ALPHA: {alpha_s:.2f}")
        self.lbl_rmssd.setText(f"RMSSD: {rmssd:.1f} ms")
        self.lbl_score.setText(f"Reducción: {(1-alpha_s)*100:.1f}%")
        self.lbl_lf.setText(f"LF: {lf:.6f} ms²")
        self.lbl_hf.setText(f"HF: {hf:.6f} ms²")
        self.lbl_lfhf.setText(f"LF/HF: {lfhf:.6f}")

        ecg_draw=ecg_seg[-5000:]
#Dibuja 1 de cada 4 muestras lo que lo hace mas fluido (1000 Hz a 250 puntos)
        step=4

#Genera el eje X
        t_ecg=np.arange(len(ecg_draw))/FS+self.segundos-len(ecg_draw)/FS
        t_eeg=np.arange(len(eeg_seg))/FS+self.segundos-len(eeg_seg)/FS

        self.curve_ecg.setData(
            t_ecg[::step],
            ecg_draw[::step]
        )

        self.curve_eeg.setData(
            t_eeg[::step],
            eeg_seg[::step]
        )

#Desplaza la grafica
        self.plot_ecg.setXRange(
            max(0,self.segundos-5),
            self.segundos,
            padding=0
        )

#Desplaza la grafica
        self.plot_eeg.setXRange(
            max(0,self.segundos-VENTANA_EEG),
            self.segundos,
            padding=0
        )

#Carga Calibracion, Prueba, Interfaz y finalmente la ejecucion 
if __name__=="__main__":

    alpha_basal,rmssd_basal,lfhf_basal=calibrar(
        "LankyCalibracion.acq"
    )

    #Sirve para abrir archivos .acq del BIOPAC, carga las señales biomédicas.
    data=bioread.read_file(
        "LankyRE.acq"
    )

    app=QApplication(sys.argv)

    gui=SemaforoGUI(
        data.channels[0].data,
        data.channels[1].data,
        alpha_basal,
        rmssd_basal,
        lfhf_basal
    )

    gui.show()

    sys.exit(app.exec_())