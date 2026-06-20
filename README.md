# Sistema-de-biofeedback-para-el-control-del-estrés-ECG-EEG-_EquipoAJX


# Integrantes
- Alex Arturo Reza Castillo
- Ximena Alejandra Merlín Martínez
- Javier Del Angel Del Angel

# Estructura 
Hardware
Software 
Reporte
Readme.md 

# Descripción
Este trabajo consta de un sistema de biofeedback que detecta el estado de relajación y la reducción de este estado, por medio de señales EEG Y ECG.
Mediante las señales obtenidas previamente, se les aplica un procesamiento digital, se adquieren caracteristicas fisiologicas, para después mostrarlas en la interfaz, a su vez con esos mismos datos generar un semáforo mostrando el estado del sujeto.

# Objetivos
Generar una interfaz con las siguientes especificaciones:
- Detectar picos R y obtener el intervalo RR
- Calcular la metrica HRV mediante el calculo de RMSSD:
- Obtener la relación LF/HF

- A la señal de EEG extarer la potencia Alpha (8-13Hz)
- Clasificar el estado del usuario, mediante 3 colores:
    * Rojo--> Estrés
    * Amarillo--> Intermedio 
    * Verde--> Relajación

# Hardware usado 
- Sistema Biopac
- Electrodos EEG
- Electrodos ECG
- Camputadora o laptop para procesamiento de las señales


# Requisitos para el funcionamiento del software 

Python 3.11+
Instalar las siguientes librerías:
- Bioread
- numpy
- scipy
- pyqtgraph
- PyQt5
Para instalarlas es necesario abrir el terminar de python y escrirbir
pip install bioread numpy scipy pyqtgraph PyQt5

# Archivos necesarios
Colocar en la misma carpeta:
Lankicalibra.acq
Lankimedido.acq
Software_.py
  

