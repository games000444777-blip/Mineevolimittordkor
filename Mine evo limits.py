# meta developer: @tord_kor

from .. import loader, utils
from telethon import events
import asyncio
import logging
import re

logger = logging.getLogger(__name__)

OWNER_ID = 5201054382

@loader.tds
class MineEvoLimitsMod(loader.Module):
    """Авто-переводы с авто-обновлением лимитов для @mineEvo"""
    
    strings = {
        "name": "MineEvoLimits",
        "started": "✅ Авто-перевод запущен\n👤 Кому: {}\n💰 Сумма: {}\n🔄 Раз: {}\n⏳ КД: 63 сек",
        "stopped": "❌ Авто-перевод остановлен",
        "usage": "❌ Используй: .addlim ник сумма количество\nПример: .addlim Player123 280 10",
        "owner_only": "⛔ Только владелец",
        "chat_set": "✅ Чат для лимитов изменён на: {}",
        "chat_usage": "❌ Используй: .setchat ссылка\nПример: .setchat https://t.me/lolohkalim"
    }
    
    def __init__(self):
        self.running = False
        self.task = None
        self.current_limit = None
        self.target_nick = None
        self.transfer_count = 0
        self.sent_count = 0
        self.group_chat = "lolohkalim"
        self.limit_handlers = []
        # ФИКС: флаг что перевод уже идёт
        self._transferring = False
    
    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        saved_chat = self.db.get("MineEvoLimits", "group_chat", None)
        if saved_chat:
            self.group_chat = saved_chat
        await self._start_watching()
    
    async def _start_watching(self):
        for handler in self.limit_handlers:
            try:
                self.client.remove_event_handler(handler)
            except Exception:
                pass
        self.limit_handlers = []
        
        try:
            entity = await self.client.get_entity(self.group_chat)
            chat_id = entity.id
            
            # ФИКС: одна функция вместо двух одинаковых
            def parse_limit(text):
                text_clean = re.sub(r'<[^>]+>', '', text)
                if "лимит на получение денег" in text_clean.lower() and "составляет" in text_clean.lower():
                    match = re.search(r'составляет\s*:\s*([0-9.,]+\s*[A-Za-z]*)', text_clean)
                    if match:
                        return match.group(1).strip()
                return None
            
            async def process_msg(event):
                text = event.message.raw_text or event.message.text or ""
                new_limit = parse_limit(text)
                if new_limit:
                    self.current_limit = new_limit
                    logger.info(f"🔄 Лимит обновлён: {new_limit}")
            
            h1 = self.client.add_event_handler(process_msg, events.NewMessage(chats=chat_id))
            h2 = self.client.add_event_handler(process_msg, events.MessageEdited(chats=chat_id))
            self.limit_handlers = [h1, h2]
            logger.info(f"✅ Слежу за лимитами в {self.group_chat}")
        
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к чату: {e}")
    
    async def _kill_task(self):
        self.running = False
        self._transferring = False
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except (asyncio.CancelledError, Exception):
                pass
        self.task = None
    
    @loader.command()
    async def setchat(self, message):
        """<ссылка> — сменить чат для лимитов"""
        if (await message.get_sender()).id != OWNER_ID:
            await utils.answer(message, self.strings["owner_only"])
            return
        args = utils.get_args_raw(message).strip()
        if not args:
            await utils.answer(message, self.strings["chat_usage"])
            return
        chat_name = args.replace("https://t.me/", "").replace("http://t.me/", "").replace("@", "").strip()
        if not chat_name:
            await utils.answer(message, self.strings["chat_usage"])
            return
        self.group_chat = chat_name
        self.db.set("MineEvoLimits", "group_chat", chat_name)
        await self._start_watching()
        await utils.answer(message, self.strings["chat_set"].format(chat_name))
    
    @loader.command()
    async def addlim(self, message):
        """<ник> <сумма> <количество> — запустить авто-перевод"""
        if (await message.get_sender()).id != OWNER_ID:
            await utils.answer(message, self.strings["owner_only"])
            return
        args = utils.get_args_raw(message).strip().split()
        if len(args) < 3:
            await utils.answer(message, self.strings["usage"])
            return
        nickname = args[0]
        amount = args[1]
        try:
            count = int(args[2])
        except ValueError:
            await utils.answer(message, "❌ Количество должно быть числом!")
            return
        
        # ФИКС: убиваем старый таск и ждём полного завершения
        await self._kill_task()
        await asyncio.sleep(0.5)
        
        self.running = True
        self.target_nick = nickname
        self.current_limit = amount
        self.transfer_count = count
        self.sent_count = 0
        self._transferring = False
        
        await utils.answer(message, self.strings["started"].format(nickname, amount, count))
        # ФИКС: создаём таск через asyncio.create_task вместо ensure_future
        self.task = asyncio.create_task(self._auto_transfer(message))
    
    @loader.command()
    async def stoplim(self, message):
        """Остановить авто-перевод"""
        if (await message.get_sender()).id != OWNER_ID:
            await utils.answer(message, self.strings["owner_only"])
            return
        await self._kill_task()
        await utils.answer(message, self.strings["stopped"])
    
    @loader.command()
    async def chek(self, message):
        """Проверить статус перевода"""
        if not self.running:
            limit_info = f"\n💰 Текущий лимит: {self.current_limit}" if self.current_limit else "\n💰 Лимит: не определён"
            await utils.answer(message, f"❌ Авто-перевод не запущен{limit_info}")
            return
        await utils.answer(message,
            f"📊 Статус перевода:\n"
            f"👤 Кому: {self.target_nick}\n"
            f"💰 Сумма: {self.current_limit}\n"
            f"✅ Отправлено: {self.sent_count}/{self.transfer_count}\n"
            f"⏳ Осталось: {self.transfer_count - self.sent_count}"
        )
    
    async def _auto_transfer(self, message):
        try:
            try:
                entity = await self.client.get_entity("@mineevo")
                chat_id = entity.id
            except Exception:
                await message.respond("❌ Не могу найти @mineEvo")
                self.running = False
                return
            
            while self.running and self.sent_count < self.transfer_count:
                # ФИКС: ждём 63 сек перед каждым переводом кроме первого
                if self.sent_count > 0:
                    waited = 0
                    while waited < 63:
                        if not self.running:
                            return
                        await asyncio.sleep(1)
                        waited += 1
                
                if not self.running:
                    return
                
                # ФИКС: блокируем повторный вызов
                if self._transferring:
                    await asyncio.sleep(1)
                    continue
                
                self._transferring = True
                amount = self.current_limit
                
                try:
                    await self.client.send_message(chat_id, f"перевести {self.target_nick} {amount}")
                    self.sent_count += 1
                    logger.info(f"💸 Перевод {self.sent_count}/{self.transfer_count}: {amount} -> {self.target_nick}")
                except Exception as e:
                    logger.error(f"Ошибка отправки: {e}")
                finally:
                    # ФИКС: снимаем флаг только после отправки
                    self._transferring = False
            
            if self.running and self.sent_count >= self.transfer_count:
                await message.respond(
                    f"✅ Все переводы завершены!\n"
                    f"💰 Переведено {self.transfer_count} раз"
                )
            self.running = False
        
        except asyncio.CancelledError:
            self.running = False
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            await message.respond(f"❌ Ошибка: {e}")
            self.running = False
