#meta developer: @Last_Mimi & @ZetGo

import yt_dlp
import shutil
import os
import re
import unicodedata
import asyncio
import tempfile  
import time
from functools import partial
from urllib.parse import urlparse, parse_qs
from .. import loader, utils
from telethon.tl.types import DocumentAttributeAudio, MessageMediaDocument, DocumentAttributeVideo


class VidDownloaderMod(loader.Module):
    """Обрабатывает видео по ссылке в инлайн режиме"""

    strings = {"name": "VidDownloader"}

    async def getvidcmd(self, message):
        """ [одна ссылка]. Выгрузка видео в указанном качестве"""
        url = [] #предполагается одна ссылка, но поставлю счётчик чтобы сказать если что "пажалста"
        self.don = False
        self.message = message
        args = message.raw_text.split(maxsplit=1)
        if len(args) > 1:
            url = self.extract_urls(args[1])
        if len(url) > 1:
            await message.respond("Не больше одной ссылки, пожалуйста")
            return
        if not url:
            await message.respond("Пожалуйста, укажите ссылку на видео")
            return
        url = url[0]
        self.url = url
        tempM = await message.respond("🔍 Получаю информацию о видео...")
        txt, self.titl, e = self.getInfo(url)
        if not txt:
            await tempM.edit(f"❎ Ничего не вышло, ошибка: {e}")
            return
        await tempM.edit("☑️ Готово! Строю меню...")
        await self.Menu(txt, message, tempM)
        
        
    def getInfo(self, u):
        """Узнаю основную информацию об обрабатывемом видео"""
        ydl_opts = {
            'no_warnings': True,
        }
        e = None
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(u, download=False)
                title = info_dict.get('title', 'unknown_title')
                channel = info_dict.get('channel', 'Ошибка')
                formats = info_dict.get("formats", [])
            settext = [{'format_id' : 'mp3', 'format_note' : 'mp3'}]
            collected = []
            for frmt in formats:
                if frmt.get('ext') == 'mp4' and frmt.get('format_note') and frmt.get('audio_codec') in [None,'none'] and frmt['format_note'] not in collected and frmt.get('format_note') not in ('Default','Premium'):
                    collected.append(frmt['format_note'])
                    settext.append( {'format_id' : frmt['format_id'], 'format_note' : frmt['format_note']})
                
            return settext, title, e
        except Exception as e:
            print(e)
            return None, None, e
        
    async def Menu(self, ids, message, toDelete):
        """Построение меню с кнопками выбора качества"""
        text = f"▶️ Видео: '{self.titl}'. \n\nВыберите формат."
        frmts_btn = []
        self.key = []
        for id in ids:
            frmts_btn.append({"text": id['format_note'], "callback": partial(self.handle_callback, f"format:{id['format_id']}f:{id['format_note']}")})
        self.key.append(frmts_btn)
        await self.inline.form(
            text=text, 
            message=message,
            reply_markup=self.key
        )
        await toDelete.delete()
        

    async def downl_choosn(self, inlmessage):
        """Скачиваем"""
        temp_dir = tempfile.mkdtemp()
        filename_base = self.extract_filename_from_url(self.url)
        fmt = f'{self.chsn}+bestaudio' if self.chsn != 'mp3' else 'bestaudio/best'
        ydl_opts = {
            'format': fmt,
            'outtmpl': os.path.join(temp_dir, f'{filename_base}.%(ext)s'),
            'no_warnings': True,
        }
        try:
            await inlmessage.edit(text="⌛")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(self.url, download=True)
                title = info_dict.get('title', 'unknown_title')
                ext = info_dict.get('ext', 'webm')
                filename = os.path.join(temp_dir, f"{filename_base}.{ext}")
                duration = info_dict.get('duration', 0)
                resolution = info_dict.get('resolution', '0x0')
                channel = info_dict.get('channel', 'неизвестен')
            if self.chsn != 'mp3':
                width, height = map(int, resolution.split('x'))
            
            if os.path.exists(filename):
                await inlmessage.edit(text=f"☑️ {'Видео скачано' if self.chsn != 'mp3' else 'Музыка скачана'}, жди {'окончания обработки и' if self.chsn == 'mp3' else ''} выгрузки!")
                try:
                    if self.chsn != 'mp3':
                        await self.client.send_message(
                            utils.get_chat_id(self.message),
                            filename, force_document=False,
                            attributes=[
                                DocumentAttributeVideo(duration=duration, h=height, w=width)],
                         )
                    else:
                        ffmpeg_location = shutil.which("ffmpeg")
                        if not ffmpeg_location:
                            raise FileNotFoundError("FFmpeg не найден. Установите его.")
                        mp3 = filename.replace(os.path.splitext(filename)[1], ".mp3")
                        ffmpeg_command = f'{ffmpeg_location} -i "{filename}" -vn -ar 44100 -ac 2 -b:a 192k "{mp3}"'
                        process = await asyncio.create_subprocess_shell(
                            ffmpeg_command,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        stdout, stderr = await process.communicate()
        
                        if process.returncode == 0 and os.path.exists(file):
                            await self.client.send_message(
                            utils.get_chat_id(self.message),
                            mp3,
                            attributes=[
                                DocumentAttributeAudio(duration=duration, title=title, performer=channel)],
                        )
                        else:
                            await inlmessage.edit(text=f"Ошибка при конвертации в MP3. Код ошибки: {process.returncode}")
                        
                    await self.clean_directory(filename)
                except Exception as e:
                    await self.message.respond(str(e))
                    await self.clean_directory(filename)
            else:
                await call.delete()
        except Exception as e:
            await self.message.respond(f"Что-то не так, ошибка: {e}")
        
        
    async def handle_callback(self, call, gotten):
        """Обработка кнопки(потом переделаю)"""
        #await self.message.respond(f"Получено: {call} и {gotten}")
        frmt = call.split("format:")[1].split("f:")[0]
        humanfrmt = call.split("f:")[1]
        self.chsn = frmt
        text = f"<emoji document_id=5334681713316479679>📱</emoji> Видео: '{self.titl}'.\n\nВы выбрали формат: {humanfrmt if humanfrmt == 'mp3' else 'mp4'}.\n\n<emoji document_id=5264971795647184318>🐇</emoji> Вы выбрали качество: {'Только звук' if humanfrmt == 'mp3' else humanfrmt}"
        downbtn = [{"text": "Скачать", "callback": self.downl_choosn}]
        if not self.don:
            self.key.append(downbtn)
            self.don = True
        await gotten.edit(text=text,reply_markup=self.key)
    
    def extract_urls(self, text):
        """Получаем ссылки"""
        if not text:
            return []
        urls = re.split(r'[;, \n]+', text.strip())
        return [url.strip() for url in urls if url.strip()]

    def extract_filename_from_url(self, url):
        """Получаем айди видео для названия файла"""
        parsed_url = urlparse(url)
        if parsed_url.query:
            query_params = parse_qs(parsed_url.query)
            return query_params.get('v', ['unknown'])[0]
        else:
            return os.path.basename(parsed_url.path)
    async def clean_directory(self, dir_path, mess=None, extension=None):
        """Удаляем файлы"""
        if mess:
            await mess.delete()
        if os.path.isfile(dir_path):
            dir_path = os.path.dirname(dir_path)
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
