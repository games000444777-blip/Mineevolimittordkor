# meta developer: @tord_kor

from .. import loader, utils
import asyncio
import logging

logger = logging.getLogger(__name__)

@loader.tds
class MineEvoLimitsMod(loader.Module):
    """Авто-переводы для @mineEvo бота"""
    
    strings = {
        "name": "MineEvoLimits",
        "started": "✅ Авто-перевод запущен\n👤 Кому: {}\n💰 Сумма: {}\n🔄 Раз: {}\n⏳ КД: 62 сек",
        "stopped": "❌ Авто-перевод остановлен",
        "done": "✅ Все переводы завершены!\n💰 Переведено {} раз по {}",
        "progress": "💸 Перевод {}/{} отправлен",
        "usage": "❌ Используй: .addlim ник сумма количество\nПример: .addlim Player123 28O 10"
    }
    
    def __init__(self):
        self.running = False
        self.task = None
    
    async def client_ready(self, client, db):
        self.client = client
        self.db = db
    
    @loader.command()
    async def addlim(self, message):
        """<ник> <сумма> <количество> — запустить авто-перевод"""
        args = utils.get_args_raw(message).strip().split()
        
        if len(args) < 3:
            await utils.answer(message, self.strings["usage"])
            return
        
        nickname = args[0]
        amount = args[1]  # Принимаем как текст (28O, 12Bb и т.д.)
        
        try:
            count = int(args[2])
        except ValueError:
            await utils.answer(message, "❌ Количество должно быть числом!")
            return
        
        if self.running:
            await utils.answer(message, "⚠️ Уже запущен! Сначала .stoplim")
            return
        
        self.running = True
        await utils.answer(message, self.strings["started"].format(nickname, amount, count))
        
        self.task = asyncio.ensure_future(self._auto_transfer(message, nickname, amount, count))
    
    @loader.command()
    async def stoplim(self, message):
        """Остановить авто-перевод"""
        self.running = False
        if self.task:
            self.task.cancel()
        await utils.answer(message, self.strings["stopped"])
    
    async def _auto_transfer(self, message, nickname, amount, count):
        try:
            try:
                entity = await self.client.get_entity("@mineevo")
                chat_id = entity.id
            except:
                await message.respond("❌ Не могу найти @mineEvo")
                self.running = False
                return
            
            sent = 0
            
            while self.running and sent < count:
                await self.client.send_message(chat_id, f"перевести {amount} {nickname}")
                sent += 1
                
                logger.info(f"💸 Перевод {sent}/{count}: {amount} -> {nickname}")
                await message.respond(self.strings["progress"].format(sent, count))
                
                if sent < count and self.running:
                    await asyncio.sleep(63)
            
            if sent >= count:
                await message.respond(self.strings["done"].format(count, amount))
            
            self.running = False
        
        except asyncio.CancelledError:
            logger.info("Авто-перевод отменён")
        except Exception as e:
            logger.error(f"Ошибка авто-перевода: {e}")
            await message.respond(f"❌ Ошибка: {e}")
            self.running = False
