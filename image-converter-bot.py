import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext
from PIL import Image, UnidentifiedImageError
from io import BytesIO
import pillow_heif
import openpyxl
from openpyxl import Workbook
import os
from datetime import datetime

# Enable HEIF/HEIC support in Pillow
pillow_heif.register_heif_opener()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)



# Replace 'YOUR_API_KEY' with your actual bot token
API_KEY = '7295844298:AAGwAe5brA5Yymk_3iMrZJXmxREfRLyK6eQ'
user_images = {}
user_image_info = {}
user_pdf_images = {}
user_states = {}
user_languages = {}
excel_file = 'user_data.xlsx'

# Initialize the Excel file if it doesn't exist
if not os.path.exists(excel_file):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'User Data'
    sheet.append(['User ID', 'Username', 'Feature Used', 'Timestamp'])
    workbook.save(excel_file)
    logger.info(f"Excel file created: {excel_file}")

# Function to log user data
def log_user_data(user_id, username, feature):
    try:
        workbook = openpyxl.load_workbook(excel_file)
        sheet = workbook['User Data']
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sheet.append([f'UserID: {user_id}', username, feature, timestamp])
        workbook.save(excel_file)
        logger.info(f"Logged data for user: {user_id}, username: {username}, feature: {feature}")
    except Exception as e:
        logger.error(f"Error logging user data: {e}")

# Start command handler
async def start(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id
    user_states[user_id] = 'language_selection'

    keyboard = [
        [InlineKeyboardButton("English", callback_data='language_english')],
        [InlineKeyboardButton("فارسی", callback_data='language_persian')],
        [InlineKeyboardButton("Türkçe", callback_data='language_turkish')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text('Please select your language:\nلطفاً زبان خود را انتخاب کنید:\nLütfen dilinizi seçin:', reply_markup=reply_markup)
    else:
        await update.callback_query.message.reply_text('Please select your language:\nلطفاً زبان خود را انتخاب کنید:\nLütfen dilinizi seçin:', reply_markup=reply_markup)

# Handle button press and language selection
async def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data.startswith('language_'):
        language = query.data.split('_')[1]
        user_languages[user_id] = language
        user_states[user_id] = 'start'

        await show_main_menu(query.message, context, user_id)
        return

    language = user_languages.get(user_id, 'english')

    if query.data == 'convert_to_pdf':
        user_states[user_id] = 'collecting_images'
        user_pdf_images[user_id] = []
        if language == 'english':
            message = 'Please send your photos (maximum 50). After sending all photos, click "Finish sending".'
        elif language == 'persian':
            message = 'لطفاً عکس‌های خود را ارسال کنید (حداکثر ۵۰ عکس). پس از ارسال همه عکس‌ها، دکمه "پایان ارسال" را انتخاب کنید.'
        elif language == 'turkish':
            message = 'Lütfen fotoğraflarınızı gönderin (en fazla 50). Tüm fotoğrafları gönderdikten sonra "Gönderimi bitir" tuşuna basın.'
        await query.edit_message_text(message)
        log_user_data(user_id, query.from_user.username, 'convert_to_pdf')

    elif query.data == 'change_format':
        user_states[user_id] = 'change_format'
        if language == 'english':
            message = 'Please send a photo or image file.'
        elif language == 'persian':
            message = 'لطفاً یک عکس یا فایل تصویری ارسال کنید.'
        elif language == 'turkish':
            message = 'Lütfen bir fotoğraf veya görüntü dosyası gönderin.'
        await query.edit_message_text(message)
        log_user_data(user_id, query.from_user.username, 'change_format')

    elif query.data == 'reduce_image_size':
        user_states[user_id] = 'reduce_image_size'
        if language == 'english':
            message = 'Please send a photo or image file.'
        elif language == 'persian':
            message = 'لطفاً یک عکس یا فایل تصویری ارسال کنید.'
        elif language == 'turkish':
            message = 'Lütfen bir fotoğraf veya görüntü dosyası gönderin.'
        await query.edit_message_text(message)
        log_user_data(user_id, query.from_user.username, 'reduce_image_size')

    elif query.data == 'finish_sending':
        await show_pdf_options(update, context)

    elif query.data == 'continue':
        await show_main_menu(query.message, context, user_id)

    elif query.data == 'end':
        if language == 'english':
            message = 'Thank you for using our service. See you again.'
            button_text = 'Start'
        elif language == 'persian':
            message = 'ممنون از استفاده شما. دوباره منتظرتان هستیم.'
            button_text = 'شروع'
        elif language == 'turkish':
            message = 'Hizmetimizi kullandığınız için teşekkür ederiz. Tekrar görüşmek üzere.'
            button_text = 'Başlat'
        await query.edit_message_text(message)
        keyboard = [[InlineKeyboardButton(button_text, callback_data='start_again')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(f'برای شروع مجدد، دکمه "{button_text}" را بزنید.', reply_markup=reply_markup)

    elif query.data == 'start_again':
        await start(query, context)

    elif query.data.startswith('format_'):
        await handle_format_change(update, context)

    elif query.data.startswith('reduce_'):
        await handle_reduce_size(update, context)

async def show_main_menu(message, context: CallbackContext, user_id) -> None:
    language = user_languages.get(user_id, 'english')

    if language == 'english':
        message_text = 'Please choose an option:'
        keyboard = [
            [InlineKeyboardButton("Convert image to PDF", callback_data='convert_to_pdf')],
            [InlineKeyboardButton("Change image format", callback_data='change_format')],
            [InlineKeyboardButton("Reduce image size", callback_data='reduce_image_size')]
        ]
    elif language == 'persian':
        message_text = 'لطفاً یک گزینه را انتخاب کنید:'
        keyboard = [
            [InlineKeyboardButton("تبدیل عکس به PDF", callback_data='convert_to_pdf')],
            [InlineKeyboardButton("تغییر فرمت عکس", callback_data='change_format')],
            [InlineKeyboardButton("کاهش حجم عکس", callback_data='reduce_image_size')]
        ]
    elif language == 'turkish':
        message_text = 'Lütfen bir seçenek seçin:'
        keyboard = [
            [InlineKeyboardButton("PDF'ye dönüştür", callback_data='convert_to_pdf')],
            [InlineKeyboardButton("Resim formatını değiştir", callback_data='change_format')],
            [InlineKeyboardButton("Resim boyutunu küçült", callback_data='reduce_image_size')]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text(message_text, reply_markup=reply_markup)

# Receive photo and handle based on state
async def receive_photo(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in user_states:
        await start(update, context)
        return

    state = user_states.get(user_id, 'start')

    if state == 'collecting_images':
        await collect_images(update, context)
    elif state == 'change_format':
        await handle_change_format_photo(update, context)
    elif state == 'reduce_image_size':
        await handle_reduce_image_photo(update, context)

async def collect_images(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    language = user_languages.get(user_id, 'english')

    if len(user_pdf_images[user_id]) >= 50:
        if language == 'english':
            message = 'The maximum number of photos for PDF is 50. Please select the "Finish sending" option.'
        elif language == 'persian':
            message = 'حداکثر تعداد عکس‌ها برای PDF ۵۰ عدد است. لطفاً گزینه "پایان ارسال" را انتخاب کنید.'
        elif language == 'turkish':
            message = 'PDF için maksimum fotoğraf sayısı 50. Lütfen "Gönderimi bitir" seçeneğini seçin.'
        await update.message.reply_text(message)
        return

    file = await context.bot.get_file(update.message.photo[-1].file_id)
    image_data = BytesIO(await file.download_as_bytearray())

    try:
        image = Image.open(image_data)
    except UnidentifiedImageError:
        if language == 'english':
            message = 'The file format is not recognized. Please send a valid photo.'
        elif language == 'persian':
            message = 'فرمت فایل شناسایی نشد. لطفاً یک عکس معتبر ارسال کنید.'
        elif language == 'turkish':
            message = 'Dosya formatı tanınmadı. Lütfen geçerli bir fotoğraf gönderin.'
        await update.message.reply_text(message)
        return

    user_pdf_images[user_id].append(image)

    if len(user_pdf_images[user_id]) == 1:
        keyboard = [[InlineKeyboardButton("Finish sending", callback_data='finish_sending')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if language == 'english':
            message = 'After sending all photos, click "Finish sending".'
        elif language == 'persian':
            message = 'پس از ارسال همه عکس‌ها، گزینه "پایان ارسال" را انتخاب کنید.'
        elif language == 'turkish':
            message = 'Tüm fotoğrafları gönderdikten sonra "Gönderimi bitir" tuşuna basın.'
        await update.message.reply_text(message, reply_markup=reply_markup)

async def handle_change_format_photo(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    language = user_languages.get(user_id, 'english')
    file_id = None
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document:
        file_id = update.message.document.file_id

    if not file_id:
        if language == 'english':
            message = 'Please send a valid photo or image file.'
        elif language == 'persian':
            message = 'لطفاً یک عکس یا فایل تصویری معتبر ارسال کنید.'
        elif language == 'turkish':
            message = 'Lütfen geçerli bir fotoğraf veya görüntü dosyası gönderin.'
        await update.message.reply_text(message)
        return

    file = await context.bot.get_file(file_id)
    image_data = BytesIO(await file.download_as_bytearray())
    user_images[user_id] = image_data

    try:
        image = Image.open(image_data)
    except UnidentifiedImageError:
        if language == 'english':
            message = 'The file format is not recognized. Please send a valid photo.'
        elif language == 'persian':
            message = 'فرمت فایل شناسایی نشد. لطفاً یک عکس معتبر ارسال کنید.'
        elif language == 'turkish':
            message = 'Dosya formatı tanınmadı. Lütfen geçerli bir fotoğraf gönderin.'
        await update.message.reply_text(message)
        return

    image_format = image.format
    image_size = image_data.getbuffer().nbytes
    user_image_info[user_id] = (image_format, image_size)

    keyboard = [
        [InlineKeyboardButton("JPEG", callback_data='format_JPEG'), InlineKeyboardButton("PNG", callback_data='format_PNG')],
        [InlineKeyboardButton("BMP", callback_data='format_BMP')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if language == 'english':
        message = f'Please select the desired format:\nCurrent format: {image_format}\nCurrent size: {image_size // 1024} KB'
    elif language == 'persian':
        message = f'لطفاً فرمت مورد نظر را انتخاب کنید:\nفرمت فعلی عکس: {image_format}\nحجم فعلی عکس: {image_size // 1024} کیلوبایت'
    elif language == 'turkish':
        message = f'Lütfen istenilen formatı seçin:\nGeçerli format: {image_format}\nGeçerli boyut: {image_size // 1024} KB'
    await update.message.reply_text(message, reply_markup=reply_markup)

# Handle format change
async def handle_format_change(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    format_choice = query.data.split('_')[1]
    image_data = user_images.get(user_id)

    if not image_data:
        language = user_languages.get(user_id, 'english')
        if language == 'english':
            message = 'No photo found for format change.'
        elif language == 'persian':
            message = 'هیچ عکسی برای تغییر فرمت یافت نشد.'
        elif language == 'turkish':
            message = 'Format değişikliği için fotoğraf bulunamadı.'
        await query.message.reply_text(message)
        return

    output = BytesIO()
    image = Image.open(image_data)
    if format_choice == 'JPG':
        format_choice = 'JPEG'  # Ensure the format is correct for saving
    image.save(output, format=format_choice)
    output.seek(0)

    await query.message.reply_document(InputFile(output, filename=f'converted.{format_choice.lower()}'))
    await continue_or_end(query.message, context)

async def handle_reduce_image_photo(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    language = user_languages.get(user_id, 'english')
    file_id = None
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document:
        file_id = update.message.document.file_id

    if not file_id:
        if language == 'english':
            message = 'Please send a valid photo or image file.'
        elif language == 'persian':
            message = 'لطفاً یک عکس یا فایل تصویری معتبر ارسال کنید.'
        elif language == 'turkish':
            message = 'Lütfen geçerli bir fotoğraf veya görüntü dosyası gönderin.'
        await update.message.reply_text(message)
        return

    file = await context.bot.get_file(file_id)
    image_data = BytesIO(await file.download_as_bytearray())
    user_images[user_id] = image_data

    try:
        image = Image.open(image_data)
    except UnidentifiedImageError:
        if language == 'english':
            message = 'The file format is not recognized. Please send a valid photo.'
        elif language == 'persian':
            message = 'فرمت فایل شناسایی نشد. لطفاً یک عکس معتبر ارسال کنید.'
        elif language == 'turkish':
            message = 'Dosya formatı tanınmadı. Lütfen geçerli bir fotoğraf gönderin.'
        await update.message.reply_text(message)
        return

    image_format = image.format
    image_size = image_data.getbuffer().nbytes
    user_image_info[user_id] = (image_format, image_size)

    keyboard = [
        [InlineKeyboardButton("۱۰٪", callback_data='reduce_10')],
        [InlineKeyboardButton("۲۰٪", callback_data='reduce_20')],
        [InlineKeyboardButton("۳۰٪", callback_data='reduce_30')],
        [InlineKeyboardButton("۴۰٪", callback_data='reduce_40')],
        [InlineKeyboardButton("۵۰٪", callback_data='reduce_50')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if language == 'english':
        message = f'Please select the reduction percentage:\nCurrent size: {image_size // 1024} KB'
    elif language == 'persian':
        message = f'لطفاً درصد کاهش حجم را انتخاب کنید:\nحجم فعلی عکس: {image_size // 1024} کیلوبایت'
    elif language == 'turkish':
        message = f'Lütfen azaltma yüzdesini seçin:\nGeçerli boyut: {image_size // 1024} KB'
    await update.message.reply_text(message, reply_markup=reply_markup)

# Handle size reduction
async def handle_reduce_size(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    reduction_choice = int(query.data.split('_')[1])
    image_data = user_images.get(user_id)

    if not image_data:
        language = user_languages.get(user_id, 'english')
        if language == 'english':
            message = 'No photo found for size reduction.'
        elif language == 'persian':
            message = 'هیچ عکسی برای کاهش حجم یافت نشد.'
        elif language == 'turkish':
            message = 'Boyut azaltma için fotoğraf bulunamadı.'
        await query.message.reply_text(message)
        return

    output = BytesIO()
    image = Image.open(image_data)
    width, height = image.size
    new_width = int(width * (1 - reduction_choice / 100))
    new_height = int(height * (1 - reduction_choice / 100))
    resized_image = image.resize((new_width, new_height), Image.ANTIALIAS)
    resized_image.save(output, format=image.format)
    output.seek(0)

    await query.message.reply_document(InputFile(output, filename=f'reduced.{image.format.lower()}'))
    await continue_or_end(query.message, context)

# Handle PDF creation (restored to previous functionality)
async def show_pdf_options(update: Update, context: CallbackContext) -> None:
    user_id = update.callback_query.from_user.id
    language = user_languages.get(user_id, 'english')
    images = user_pdf_images.get(user_id, [])

    if not images:
        if language == 'english':
            message = 'No photos found for PDF creation.'
        elif language == 'persian':
            message = 'هیچ عکسی برای تبدیل به PDF یافت نشد.'
        elif language == 'turkish':
            message = 'PDF oluşturmak için fotoğraf bulunamadı.'
        await update.callback_query.edit_message_text(message)
        return

    if language == 'english':
        message = 'Files received and being converted to PDF...'
    elif language == 'persian':
        message = 'فایل‌ها دریافت شد و در حال تبدیل به PDF هستند...'
    elif language == 'turkish':
        message = 'Dosyalar alındı ve PDF\'ye dönüştürülüyor...'
    await update.callback_query.edit_message_text(message)

    pdf_output = BytesIO()
    images[0].save(pdf_output, format='PDF', save_all=True, append_images=images[1:])
    pdf_output.seek(0)

    await update.callback_query.message.reply_document(InputFile(pdf_output, filename='converted.pdf'))
    await continue_or_end(update.callback_query.message, context)

async def continue_or_end(update: Update, context: CallbackContext) -> None:
    language = user_languages.get(update.from_user.id, 'english')
    if language == 'english':
        message = 'Do you want to continue?'
    elif language == 'persian':
        message = 'آیا می‌خواهید ادامه دهید؟'
    elif language == 'turkish':
        message = 'Devam etmek istiyor musunuz?'

    keyboard = [
        [InlineKeyboardButton("Continue", callback_data='continue')],
        [InlineKeyboardButton("Exit", callback_data='end')]
    ]
    if language == 'persian':
        keyboard = [
            [InlineKeyboardButton("ادامه", callback_data='continue')],
            [InlineKeyboardButton("خروج", callback_data='end')]
        ]
    elif language == 'turkish':
        keyboard = [
            [InlineKeyboardButton("Devam", callback_data='continue')],
            [InlineKeyboardButton("Çıkış", callback_data='end')]
        ]
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.reply_text(message, reply_markup=reply_markup)

def main() -> None:
    application = Application.builder().token(API_KEY).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, receive_photo))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(CallbackQueryHandler(handle_format_change, pattern='format_'))
    application.add_handler(CallbackQueryHandler(handle_reduce_size, pattern='reduce_'))

    application.run_polling()

if __name__ == '__main__':
    main()