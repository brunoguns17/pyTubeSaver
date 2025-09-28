import os
import re
import subprocess
import threading
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pytubefix import YouTube

def get_application_path():
    """
    Retorna o caminho base da aplicação.
    Se o aplicativo estiver congelado (por exemplo, com PyInstaller), utiliza sys._MEIPASS.
    Caso contrário, retorna o diretório do arquivo atual.
    """
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

# Obtém o caminho base
base_path = get_application_path()

# Define o nome do executável do FFmpeg dependendo do sistema operacional
if os.name == 'nt':  # Windows
    ffmpeg_executable = 'ffmpeg.exe'
else:
    ffmpeg_executable = 'ffmpeg'

# Define o caminho relativo para o FFmpeg (a pasta "ffmpeg" deve estar na mesma pasta deste script)
ffmpeg_path = os.path.join(base_path, 'ffmpeg', ffmpeg_executable)

class AdaptiveDownloaderGUI:
    def __init__(self, master):
        self.master = master
        master.title("Download de Vídeo / Áudio")
        
        # Linha 0: URL do vídeo
        self.url_label = tk.Label(master, text="URL do Vídeo:")
        self.url_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.url_entry = tk.Entry(master, width=50)
        self.url_entry.grid(row=0, column=1, padx=5, pady=5)
        self.load_button = tk.Button(master, text="Carregar Vídeo", command=self.load_video)
        self.load_button.grid(row=0, column=2, padx=5, pady=5)
        
        # Linha 1: Seleção da qualidade de vídeo (usado apenas no modo Vídeo e Áudio)
        self.quality_label = tk.Label(master, text="Qualidade de Vídeo:")
        self.quality_label.grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.quality_var = tk.StringVar()
        self.quality_combo = ttk.Combobox(master, textvariable=self.quality_var, state="readonly", width=40)
        self.quality_combo.grid(row=1, column=1, columnspan=2, padx=5, pady=5)
        
        # Linha 2: Seleção da pasta de destino
        self.folder_label = tk.Label(master, text="Pasta de Destino:")
        self.folder_label.grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.folder_var = tk.StringVar()
        self.folder_var.set(os.getcwd())
        self.folder_entry = tk.Entry(master, textvariable=self.folder_var, width=50, state="readonly")
        self.folder_entry.grid(row=2, column=1, padx=5, pady=5)
        self.folder_button = tk.Button(master, text="Selecionar Pasta", command=self.select_folder)
        self.folder_button.grid(row=2, column=2, padx=5, pady=5)
        
        # Linha 3: Opção para converter o áudio
        self.audio_format_label = tk.Label(master, text="Converter Áudio Para:")
        self.audio_format_label.grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.audio_format_var = tk.StringVar()
        self.audio_format_var.set("Nenhum")
        self.audio_format_options = ["Nenhum", "MP3", "WAV"]
        self.audio_format_menu = tk.OptionMenu(master, self.audio_format_var, *self.audio_format_options)
        self.audio_format_menu.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        
        # Linha 4: Seleção da qualidade do áudio
        self.audio_quality_label = tk.Label(master, text="Qualidade do Áudio:")
        self.audio_quality_label.grid(row=4, column=0, padx=5, pady=5, sticky="e")
        self.audio_quality_var = tk.StringVar()
        self.audio_quality_var.set("Padrão")
        self.audio_quality_options = ["Padrão", "64k", "128k", "192k", "320k"]
        self.audio_quality_combo = ttk.Combobox(master, textvariable=self.audio_quality_var, 
                                                 values=self.audio_quality_options, state="readonly", width=20)
        self.audio_quality_combo.grid(row=4, column=1, padx=5, pady=5, sticky="w")
        
        # Linha 5: Modo de Download – Label
        self.download_mode_label = tk.Label(master, text="Modo de Download:")
        self.download_mode_label.grid(row=5, column=0, padx=5, pady=5, sticky="e")
        self.download_mode_var = tk.StringVar()
        self.download_mode_var.set("Vídeo e Áudio")
        
        # Linha 6: Modo de Download – Opção Vídeo (radio button)
        self.mode_video_radio = tk.Radiobutton(master, text="Vídeo", variable=self.download_mode_var, value="Vídeo e Áudio")
        self.mode_video_radio.grid(row=6, column=0, columnspan=3, sticky="w", padx=5, pady=2)
        
        # Linha 7: Modo de Download – Opção Apenas Áudio (radio button)
        self.mode_audio_radio = tk.Radiobutton(master, text="Apenas Áudio", variable=self.download_mode_var, value="Apenas Áudio")
        self.mode_audio_radio.grid(row=7, column=0, columnspan=3, sticky="w", padx=5, pady=2)
        
        # Linha 8: Botão para iniciar o download
        self.download_button = tk.Button(master, text="Download", command=self.start_download, state="disabled")
        self.download_button.grid(row=8, column=0, columnspan=3, pady=10)
        
        # Linha 9: Barra de progresso
        self.progress_bar = ttk.Progressbar(master, orient="horizontal", length=300, mode="determinate")
        self.progress_bar.grid(row=9, column=0, columnspan=3, padx=5, pady=5)
        
        # Linha 10: Rótulo de progresso (inicia vazio)
        self.progress_label = tk.Label(master, text="")
        self.progress_label.grid(row=10, column=0, columnspan=3, padx=5, pady=5)
        
        # Linha 11: Botão para abrir a pasta de destino
        self.open_folder_button = tk.Button(master, text="Abrir Pasta", command=self.open_folder)
        self.open_folder_button.grid(row=11, column=0, columnspan=3, pady=5)
        
        # Variáveis de controle
        self.yt = None
        self.video_streams_mapping = {}  # Mapeia índice -> stream (apenas vídeo)
        self.current_download = None     # "video" ou "audio"
        
        # Define o caminho do FFmpeg (usando o caminho relativo)
        self.ffmpeg_path = ffmpeg_path

    def reset_progress(self):
        """Reseta a barra de progresso e esconde o rótulo."""
        self.progress_bar['value'] = 0
        self.progress_label.config(text="")
    
    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_var.set(folder)
    
    def open_folder(self):
        folder = self.folder_var.get()
        if os.path.exists(folder):
            try:
                if os.name == 'nt':  # Windows
                    os.startfile(folder)
                elif sys.platform == "darwin":  # macOS
                    subprocess.Popen(["open", folder])
                else:  # Linux e outros
                    subprocess.Popen(["xdg-open", folder])
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível abrir a pasta: {e}")
        else:
            messagebox.showerror("Erro", "Pasta não encontrada.")
    
    def on_progress(self, stream, chunk, bytes_remaining):
        total_size = stream.filesize
        bytes_downloaded = total_size - bytes_remaining
        percent = int(bytes_downloaded * 100 / total_size)
        if self.current_download == "video":
            overall = int(percent * 0.5)  # 0 a 50%
        elif self.current_download == "audio":
            if self.download_mode_var.get() == "Vídeo e Áudio":
                overall = 50 + int(percent * 0.5)  # 50 a 100%
            else:
                overall = percent
        else:
            overall = percent
        self.master.after(0, lambda: self.update_progress(overall))
    
    def load_video(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Erro", "Insira a URL do vídeo.")
            return
        
        self.progress_label.config(text="Carregando vídeo...")
        self.download_button.config(state="disabled")
        self.quality_combo.set("")
        
        def task():
            try:
                self.yt = YouTube(url, on_progress_callback=self.on_progress)
                if self.download_mode_var.get() == "Vídeo e Áudio":
                    video_streams = self.yt.streams.filter(adaptive=True, only_video=True, file_extension="mp4").order_by("resolution").desc()
                    streams_filtered = []
                    for s in video_streams:
                        if s.resolution:
                            try:
                                res = int(s.resolution.rstrip("p"))
                                if 360 <= res <= 2160:
                                    streams_filtered.append(s)
                            except Exception as e:
                                print(f"Erro convertendo resolução: {e}")
                    if not streams_filtered:
                        streams_filtered = list(video_streams)
                    self.video_streams_mapping = {i+1: stream for i, stream in enumerate(streams_filtered)}
                    options = [f"{i}: {stream.resolution} - {stream.fps}fps" for i, stream in self.video_streams_mapping.items()]
                    self.master.after(0, lambda: self.quality_combo.config(values=options))
                    if options:
                        self.master.after(0, lambda: self.quality_combo.current(0))
                    title = self.yt.title
                    self.master.after(0, lambda: self.progress_label.config(text=f"Vídeo carregado: {title}"))
                else:
                    title = self.yt.title
                    self.master.after(0, lambda: self.progress_label.config(text=f"Áudio carregado: {title}"))
                self.master.after(0, lambda: self.download_button.config(state="normal"))
            except Exception as e:
                self.master.after(0, lambda: messagebox.showerror("Erro", f"Erro ao carregar vídeo: {e}"))
                self.master.after(0, lambda: self.progress_label.config(text="Erro ao carregar vídeo."))
        threading.Thread(target=task).start()
    
    def update_progress(self, percent):
        self.progress_bar['value'] = percent
        # Enquanto o download está em progresso, exibe "Progresso: X%"
        self.progress_label.config(text=f"Progresso: {percent}%")
    
    def start_download(self):
        if not self.yt:
            messagebox.showerror("Erro", "Carregue um vídeo primeiro.")
            return
        
        dest_folder = self.folder_var.get()
        if not os.path.exists(dest_folder):
            os.makedirs(dest_folder)
        
        mode = self.download_mode_var.get()
        # Durante o download, o rótulo será atualizado via update_progress
        self.progress_label.config(text="Progresso: 0%")
        self.progress_bar['value'] = 0
        
        def download_task():
            try:
                safe_title = re.sub(r'[\\/*?:"<>|]', "", self.yt.title)
                if mode == "Vídeo e Áudio":
                    selected = self.quality_combo.get()
                    if not selected:
                        messagebox.showerror("Erro", "Selecione uma qualidade de vídeo.")
                        return
                    try:
                        index = int(selected.split(":")[0])
                    except Exception:
                        messagebox.showerror("Erro", "Qualidade inválida selecionada.")
                        return
                    video_stream = self.video_streams_mapping.get(index)
                    if not video_stream:
                        messagebox.showerror("Erro", "Stream de vídeo não encontrada.")
                        return
                    
                    self.current_download = "video"
                    print("Iniciando download do vídeo...")
                    video_file = video_stream.download(output_path=dest_folder, filename_prefix="video_")
                    print(f"Vídeo baixado: {video_file}")
                    
                    self.current_download = "audio"
                    audio_stream = self.yt.streams.filter(only_audio=True).order_by("abr").desc().first()
                    if not audio_stream:
                        raise Exception("Nenhuma stream de áudio encontrada.")
                    print("Iniciando download do áudio...")
                    audio_file = audio_stream.download(output_path=dest_folder, filename_prefix="audio_")
                    print(f"Áudio baixado: {audio_file}")
                    
                    self.master.after(0, lambda: self.update_progress(100))
                    
                    output_filename = f"{safe_title}.mp4"
                    output_path = os.path.join(dest_folder, output_filename)
                    self.master.after(0, lambda: self.progress_label.config(text="Mesclando vídeo e áudio..."))
                    print("Iniciando mesclagem com FFmpeg...")
                    merge_command = f'"{self.ffmpeg_path}" -y -i "{video_file}" -i "{audio_file}" -c:v copy -c:a aac "{output_path}"'
                    
                    try:
                        subprocess.run(merge_command, shell=True, check=True)
                    except subprocess.CalledProcessError as e:
                        print(f"Erro ao executar FFmpeg: {e}")
                        self.master.after(0, lambda: messagebox.showerror("Erro", f"Erro ao executar FFmpeg: {e}"))
                        return
                    
                    print("Mesclagem concluída.")
                    
                    # Remove arquivos temporários
                    os.remove(video_file)
                    os.remove(audio_file)
                    self.master.after(0, lambda: messagebox.showinfo("Sucesso", "Download e mesclagem concluídos!"))
                    # Após 3 segundos, reseta a barra de progresso e esconde o rótulo
                    self.master.after(3000, self.reset_progress)
                else:  # Apenas Áudio
                    print("Iniciando download apenas de áudio...")
                    audio_stream = self.yt.streams.filter(only_audio=True).order_by("abr").desc().first()
                    if not audio_stream:
                        raise Exception("Nenhuma stream de áudio encontrada.")
                    
                    audio_file = audio_stream.download(output_path=dest_folder, filename_prefix="audio_")
                    print(f"Áudio baixado: {audio_file}")
                    
                    # Se o usuário deseja converter o áudio, realiza a conversão
                    if self.audio_format_var.get() != "Nenhum":
                        target_format = self.audio_format_var.get().lower()  # 'mp3' ou 'wav'
                        quality = self.audio_quality_var.get()
                        quality_str = quality if quality != "Padrão" else "128k"
                        converted_filename = f"{safe_title}.{target_format}"
                        converted_path = os.path.join(dest_folder, converted_filename)
                        conversion_command = f'"{self.ffmpeg_path}" -y -i "{audio_file}" -vn -ar 44100 -ac 2 -b:a {quality_str} "{converted_path}"'
                        try:
                            subprocess.run(conversion_command, shell=True, check=True)
                            os.remove(audio_file)  # Remove o arquivo original após a conversão
                            audio_file = converted_path
                            print(f"Áudio convertido para {target_format}: {audio_file}")
                        except subprocess.CalledProcessError as e:
                            print(f"Erro na conversão do áudio: {e}")
                            self.master.after(0, lambda: messagebox.showerror("Erro", f"Erro na conversão do áudio: {e}"))
                            return
                    
                    self.master.after(0, lambda: self.update_progress(100))
                    self.master.after(0, lambda: messagebox.showinfo("Sucesso", "Download concluído!"))
                    self.master.after(3000, self.reset_progress)
                    
            except Exception as e:
                print(f"Erro no download: {e}")
                self.master.after(0, lambda: messagebox.showerror("Erro", f"Erro no download: {e}"))
        threading.Thread(target=download_task).start()

def main():
    root = tk.Tk()
    app = AdaptiveDownloaderGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
