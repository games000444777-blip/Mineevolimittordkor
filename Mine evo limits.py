# meta developer: @tord_kor

from .. import loader, utils
from telethon import events
import asyncio
import logging
import re

logger = logging.getLogger(__name__)

OWNER_ID = 5201054382
GROUP_CHAT = "lolohkalim"

@loader.tds
class MineEvoLimitsMod(loader.Module):
    """Авто-переводы с авто-обновлением лимитов для @mineEvo"""
    
    strings = {
        "name": "MineEvoLimits",
        "started": "✅ Авто-перевод запущен\n👤 Кому: {}\n💰 Сумма: {}\n🔄 Раз: {}\n⏳ КД: 62 сек",
        "stopped": "❌ Авто-перевод остановлен",
        "usage": "❌ Используй: .addlim ник сумма количество\nПример: .addlim Player123 28O 10",
        "owner_only": "⛔ Только владелец"
    }
    
    def __init__(self):
        self.running = False
        self.task = None
        self.current_limit = None
        self.target_nick = None
        self.transfer_count = 0
        self.sent_count = 0
    
    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        asyncio.ensure_future(self._watch_limits())
    
    async def _watch_limits(self):
        try:
            entity = await self.client.get_entity(GROUP_CHAT)
            chat_id = entity.id
            
            logger.info(f"✅ Слежу за лимитами в чате {chat_id}")
            
            async def process_limit(event):
                msg = event.message
                text = msg.text or ""
                
                if "твой лимит на получение денег" in text.lower() and "составляет" in text.lower():
                    match = re.search(r'составляет\s*:\s*([0-9.,]+\s*[A-Za-z]*)', text)
                    if match:
                        new_limit = match.group(1).strip()
                        self.current_limit = new_limit
                        logger.info(f"🔄 Лимит обновлён: {new_limit}")
            
            self.client.add_event_handler(process_limit, events.NewMessage(chats=chat_id))
        
        except Exception as e:
            logger.error(f"❌ Ошибка слежки за лимитами: {e}")
    
    @loader.command()
    async def addlim(self, message):
        """<ник> <сумма> <количество> — запустить авто-перевод"""
        user_id = (await message.get_sender()).id
        if user_id != OWNER_ID:
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
        
        if self.running:
            await utils.answer(message, "⚠️ Уже запущен! Сначала .stoplim")
            return
        
        self.running = True
        self.target_nick = nickname
        self.current_limit = amount
        self.transfer_count = count
        self.sent_count = 0
        
        await utils.answer(message, self.strings["started"].format(nickname, amount, count))
        self.task = asyncio.ensure_future(self._auto_transfer(message))
    
    @loader.command()
    async def stoplim(self, message):
        """Остановить авто-перевод"""
        user_id = (await message.get_sender()).id
        if user_id != OWNER_ID:
            await utils.answer(message, self.strings["owner_only"])
            return
        
        self.running = False
        if self.task:
            self.task.cancel()
        await utils.answer(message, self.strings["stopped"])
    
    @loader.command()
    async def chek(self, message):
        """Проверить статус перевода"""
        if not self.running:
            await utils.answer(message, "❌ Авто-перевод не запущен")
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
            except:
                await message.respond("❌ Не могу найти @mineEvo")
                self.running = False
                return
            
            while self.running and self.sent_count < self.transfer_count:
                amount = self.current_limit
                
                await self.client.send_message(chat_id, f"перевести {self.target_nick} {amount}")
                self.sent_count += 1
                
                logger.info(f"💸 Перевод {self.sent_count}/{self.transfer_count}: {amount} -> {self.target_nick}")
                
                if self.sent_count < self.transfer_count and self.running:
                    await asyncio.sleep(63)
            
            if self.sent_count >= self.transfer_count:
                await message.respond(
                    f"✅ Все переводы завершены!\n"
                    f"💰 Переведено {self.transfer_count} раз"
                )
            
            self.running = False
        
        except asyncio.CancelledError:
            logger.info("Авто-перевод отменён")
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            await message.respond(f"❌ Ошибка: {e}")
            self.running = False
