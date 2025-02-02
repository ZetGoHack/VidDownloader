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


class vidDownloaderMod(loader.Module):
    """Обрабатывает видео по ссылке в инлайн режиме"""

    strings = {"name": "vidDownloader"}

    async def musiccmd(self, message):
        """ [ссылки на видео/ответ на сообщение с ссылками]. Скачивает и конвертирует видео в аудиофайл."""
        urls = []
        if message.is_reply:
            reply_msg = await message.get_reply_message()
            urls = self.extract_urls(reply_msg.raw_text)
        if not urls:
            args = message.raw_text.split(maxsplit=1)
            if len(args) > 1:
                urls = self.extract_urls(args[1])
        if not urls:
            await message.respond("Пожалуйста, укажите хотя бы одну ссылку")
            return

        for url in urls:
            await self.process_video(url, message)

    async def videocmd(self, message):
        """ [видеофайл/ответ]. Конвертация в аудиофайл прикреплённого видео или ответа на сообщение с видео"""
        if message.is_reply:
            reply_msg = await message.get_reply_message()
            if reply_msg and isinstance(reply_msg.media, MessageMediaDocument):
                await self.process_attached_video(reply_msg, message)
                return
        if isinstance(message.media, MessageMediaDocument):
            await self.process_attached_video(message, message)
        else:
            await message.respond("Пожалуйста, прикрепите видео или ответьте на сообщение с видео.")

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
            settext = []
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
        text = f"▶️ Видео: '{self.titl}'.\n\nВы выбрали формат: mp4."
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
        """Скачиваем видео"""
        temp_dir = tempfile.mkdtemp()
        filename_base = self.extract_filename_from_url(self.url)
        fmt = f"{self.chsn}+bestaudio"
        ydl_opts = {
            'format': fmt,
            'outtmpl': os.path.join(temp_dir, f'{filename_base}.%(ext)s'),
            'no_warnings': True,
        }
        try:
            await inlmessage.edit(text="⌛")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(self.url, download=True)
                ext = info_dict.get('ext', 'webm')
                filename = os.path.join(temp_dir, f"{filename_base}.{ext}")
                duration = info_dict.get('duration', 0)
                resolution = info_dict.get('resolution', '0x0')
                
                
            width, height = map(int, resolution.split('x'))
            
            if os.path.exists(filename):
                await inlmessage.edit(text="☑️ Видео скачано, жди выгрузки!")
                try:
                    await self.client.send_message(
                    utils.get_chat_id(self.message),
                    file=filename, force_document=False,
                     attributes=[
                         DocumentAttributeVideo(duration=duration, h=height, w=width)],
                     )
                    await self.clean_directory(filename)
                except Exception as e:
                    await self.message.respond(str(e))
                    await self.clean_directory(filename)
            else:
                await call.delete()
        except Exception as e:
            await message.respond(f"Что-то не так, ошибка: {e}")
        
        
    async def handle_callback(self, call, gotten):
        """Обработка кнопки(потом переделаю)"""
        #await self.message.respond(f"Получено: {call} и {gotten}")
        frmt = call.split("format:")[1].split("f:")[0]
        humanfrmt = call.split("f:")[1]
        self.chsn = frmt
        text = f"<emoji document_id=5334681713316479679>📱</emoji> Видео: '{self.titl}'.\n\nВы выбрали формат: mp4.\n\n<emoji document_id=5264971795647184318>🐇</emoji> Вы выбрали качество: {humanfrmt}"
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

    def clean_youtube_url(self, url):
        """Нам нужен только ютуб"""
        parsed_url = urlparse(url)
        if "youtube" in parsed_url.netloc or "youtu.be" in parsed_url.netloc:
            return url  
        return None

    def extract_filename_from_url(self, url):
        """Получаем айди видео для названия файла"""
        parsed_url = urlparse(url)
        if parsed_url.query:
            query_params = parse_qs(parsed_url.query)
            return query_params.get('v', ['unknown'])[0]
        else:
            return os.path.basename(parsed_url.path)

    async def process_video(self, url, message):
        """Обрабатываем видео по ссылке"""
        clean_url = self.clean_youtube_url(url)
        if not clean_url:
            return
        status_message = await message.respond(f"Начинаю обработку ссылки: {clean_url}\nСкачивание: [⌛] Обработка: [ ] Отправка: [ ]")
        start_time = time.time()
        file_info = await self.download_video(clean_url)
        if file_info:
            end_time = time.time()
            down_time = end_time - start_time
            await status_message.edit(f"Скачивание: [✅] Обработка: [⌛] Отправка: [ ]\nПрошло времени[На скачивание]: {down_time:.2f} секунд")
            start_time = time.time()
            file_path, duration, title, channel = await self.convert_to_mp3(file_info, status_message)
            
            if file_path:
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                end_time = time.time()
                ffmpeg_time = end_time - start_time
                await status_message.edit(f"Скачивание: [✅] Обработка: [✅] Отправка: [⌛]\nРазмер файла: {file_size_mb:.2f} МБ\nПрошло времени[На скачивание]: {down_time:.2f} секунд\nПрошло времени[На обработку]: {ffmpeg_time:.2f} секунд")
                start_time = time.time()
                await message.client.send_file(
                    message.chat_id,
                    file_path,
                    attributes=[DocumentAttributeAudio(duration=duration, title=title,performer=channel)],
                )
                os.remove(file_path)
                end_time = time.time()
                send_time = end_time - start_time
                me = await self._client.get_me()
                user_id = me.id
                await status_message.edit(f"Скачивание: [✅] Обработка: [✅] Отправка: [✅]\nРазмер файла: {file_size_mb:.2f} МБ\nПрошло времени[На скачивание]: {down_time:.2f} секунд\nПрошло времени[На обработку]: {ffmpeg_time:.2f} секунд\nПрошло времени[На отправку]: {send_time:.2f} секунд")
                #await self._client.send_message(user_id,f"Скачивание: [✅] Обработка: [✅] Отправка: [✅]\nРазмер файла: {file_size_mb:.2f} МБ\nПрошло времени[На скачивание]: {down_time:.2f} секунд\nПрошло времени[На обработку]: {ffmpeg_time:.2f} секунд\nПрошло времени[На отправку]: {send_time:.2f} секунд")
                await self.clean_directory(os.path.dirname(file_path), status_message)
            else:
                await status_message.edit(f"Ошибка при обработке ссылки: {clean_url}")
        else:
            await status_message.edit(f"Ошибка при скачивании видео: {clean_url}")

    async def download_video(self, url):
        """Скачиваем видео с YouTube"""
        temp_dir = tempfile.mkdtemp()
        filename_base = self.extract_filename_from_url(url)
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(temp_dir, f'{filename_base}.%(ext)s'),
            'no_warnings': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                title = info_dict.get('title', 'unknown_title')
                ext = info_dict.get('ext', 'webm')
                filename = os.path.join(temp_dir, f"{filename_base}.{ext}")
                duration = info_dict.get('duration', 0)
                channel = info_dict.get('channel', 'неизвестен')
            if os.path.exists(filename):
                return filename, duration, title, channel
            else:
                return None
        except Exception as e:
            print(e)
            return None

    async def convert_to_mp3(self, file_info, status_message):
        """Конвертируем видео в MP3"""
        #ffmpeg_location = "/usr/bin/ffmpeg"
        ffmpeg_location = shutil.which("ffmpeg")
        if not ffmpeg_location:
            raise FileNotFoundError("FFmpeg не найден. Установите его.")
        video_file, duration, title, channel = file_info
        output_mp3_path = video_file.replace(os.path.splitext(video_file)[1], ".mp3")
        ffmpeg_command = f'{ffmpeg_location} -i "{video_file}" -vn -ar 44100 -ac 2 -b:a 192k "{output_mp3_path}"'
        
        process = await asyncio.create_subprocess_shell(
            ffmpeg_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0 and os.path.exists(output_mp3_path):
            os.remove(video_file)
            return output_mp3_path, duration, title, channel
        else:
            await status_message.edit(f"Ошибка при конвертации видео в MP3. Код ошибки: {process.returncode}")
            return None


    async def process_attached_video(self, video_message, message):
        """Обрабатываем видео"""
        status_message = await message.respond("Начинаю обработку видео\nСкачивание: [⌛] Обработка: [ ] Отправка: [ ]")
        
        start_time = time.time()
        file_info = await self.download_and_convert_video_to_mp3(video_message, status_message, start_time)
        if file_info:
            

            file_path, duration, title, down_time, ff_time = file_info
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            start_time = time.time()
            await message.client.send_file(
                message.chat_id,
                file_path,
                attributes=[DocumentAttributeAudio(duration=duration, title=title or "VidToMusic @last_mimi")],
            )
            end_time = time.time()
            send_time = end_time - start_time
            me = await self._client.get_me()
            user_id = me.id
            await self._client.send_message(user_id,f"Скачивание: [✅] Обработка: [✅] Отправка: [✅]\nРазмер файла: {file_size_mb:.2f} МБ\nПрошло времени[На скачивание]: {down_time:.2f} секунд\nПрошло времени[На обработку]: {ff_time:.2f} секунд\nПрошло времени[На отправку]: {send_time:.2f} секунд")

            os.remove(file_path)
            await self.clean_directory(os.path.dirname(file_path), status_message, '.mp3')
        else:
            await status_message.edit("Ошибка при обработке видео")

    async def download_and_convert_video_to_mp3(self, video_message, status_message, start_time):
        """Скачивает видео из сообщения и конвертирует в MP3"""
        temp_dir = tempfile.mkdtemp()
        
        try:
            passed = False
            video_file = await video_message.download_media(file=temp_dir)
            if not video_file:
                await status_message.edit("Ошибка при скачивании видео.")
                return None
            end_time = time.time()
            down_time = end_time - start_time
            await status_message.edit(f"Скачивание: [✅] Обработка: [⌛] Отправка: [ ]\nПрошло времени[На скачивание]: {down_time:.2f} секунд")
            
            
            start_time = time.time()
            ffmpeg_location = shutil.which("ffmpeg")
            if not ffmpeg_location:
                raise FileNotFoundError("FFmpeg не найден. Установите его.")
            output_mp3_path = video_file.replace(os.path.splitext(video_file)[1], ".mp3")
            ffmpeg_command = f'{ffmpeg_location} -i "{video_file}" -vn -ar 44100 -ac 2 -b:a 192k "{output_mp3_path}"'
            
            process = await asyncio.create_subprocess_shell(
                ffmpeg_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            passed = f"{output_mp3_path}"
            file_size_mb = os.path.getsize(output_mp3_path) / (1024 * 1024)
            
            end_time = time.time()
            ff_time = end_time - start_time
            await status_message.edit(f"Скачивание: [✅] Обработка: [✅] Отправка: [⌛]\nРазмер файла: {file_size_mb:.2f} МБ\nПрошло времени[На скачивание]: {down_time:.2f} секунд\nПрошло времени[На обработку]: {ff_time:.2f} секунд")

            if process.returncode == 0 and os.path.exists(output_mp3_path):
                os.remove(video_file)
                duration = 0
                title = "YouTubeDownloader"
                return output_mp3_path, duration, title, down_time, ff_time
            else:
                await status_message.edit(f"Ошибка при конвертации видео в MP3. Код ошибки: {process.returncode}")
                return None
        except Exception as e:
            await status_message.edit(f"Ошибка при обработке видео: {str(e)}. {passed}")
            await self.clean_directory(temp_dir, status_message)
            return None
    async def clean_directory(self, dir_path, mess=None, extension=None):
        """Удаляем файлы"""
        if mess:
            await mess.delete()
        if os.path.isfile(dir_path):
            dir_path = os.path.dirname(dir_path)
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
