# راهنمای استقرار AntiScam Guardian روی Railway

این روش به VPS و دامنه اختصاصی نیاز ندارد. Railway یک دامنه HTTPS از نوع `*.up.railway.app` ایجاد می‌کند. برنامه شامل API و یک Poller تلگرام در یک سرویس است و SQLite روی Volume پایدار ذخیره می‌شود.

## مرحله صفر — بارگذاری بسته نسخه

۱. فایل `AntiScamGuardian-0.2.4-Railway.zip` را از ChatGPT دانلود کن.
۲. صفحه بارگذاری شاخه زیر را باز کن:
   `https://github.com/zior6645-rgb/anti-scam-guardian-/upload/railway-deploy-024`
۳. همان فایل ZIP را در ریشه مخزن بارگذاری کن؛ نام فایل را تغییر نده.
۴. گزینه Commit changes را بزن و شاخه `railway-deploy-024` را انتخاب کن.

پس از بارگذاری، GitHub Actions باید این کارها را انجام دهد: ۳۰ تست Python، build رابط Mini App با npm و ساخت Docker. تا وقتی همه مراحل سبز نشده‌اند، پروژه را Deploy نکن.

## مرحله یک — Railway

۱. به https://railway.com برو و با همان حساب GitHub وارد شو.
۲. از New Project گزینه Deploy from GitHub Repo را بزن.
۳. مخزن `zior6645-rgb/anti-scam-guardian-` را انتخاب کن.
۴. پس از تأیید CI و ادغام شاخه، Railway باید از Dockerfile ریشه استفاده کند.

## مرحله دو — متغیرهای محرمانه

در Settings / Variables سرویس، این متغیرها را اضافه کن:

```env
BOT_TOKEN=توکن_جدید_BotFather
BOT_USERNAME=AntiScamGuardianSafe2026Bot
ENVIRONMENT=production
ALLOW_DEV_AUTH=false
DATABASE_PATH=/data/guardian.sqlite3
FREE_SCANS_PER_DAY=5
TELEGRAM_INITDATA_MAX_AGE_SECONDS=86400
PAYMENTS_MODE=disabled
STARS_MONTHLY_PRICE=0
TON_API_BASE_URL=https://tonapi.io/v2
```

توکن را فقط در داشبورد Railway وارد کن؛ هرگز آن را در GitHub، فایل ZIP، چت یا پیام عمومی قرار نده. اگر توکن قبلی را در جایی افشا کرده‌ای، در BotFather آن را باطل کن و توکن تازه بساز.

Railway متغیر `PORT` را خودکار می‌سازد. پس از فعال‌سازی دامنه، برنامه `RAILWAY_PUBLIC_DOMAIN` را خودکار می‌خواند؛ نیازی به ثبت دستی `PUBLIC_BASE_URL` یا `WEBAPP_URL` نیست.

متغیرهای اختیاری:
- `TONAPI_KEY`: برای افزایش سقف/کیفیت درخواست‌های API در صورت نیاز.
- `PHISHTANK_APP_KEY`: فقط در صورت داشتن کلید مجاز سرویس و رعایت رضایت کاربر.

## مرحله سه — Volume و دامنه

۱. در سرویس Railway یک Volume اضافه کن و Mount Path را دقیقاً `/data` بگذار.
۲. تعداد Replica را دقیقاً **۱** نگه دار؛ ربات از long polling استفاده می‌کند و دیتابیس SQLite برای چند replica طراحی نشده است.
۳. در Settings → Networking گزینه Generate Domain را بزن.
۴. منتظر بمان تا دامنه عمومی HTTPS ساخته شود و سرویس مجدداً Deploy شود.

## مرحله چهار — آزمون بعد از استقرار

آدرس دامنه تولیدشده را در مرورگر باز کن:
- `/health` باید JSON سالم و نسخه 0.2.4 برگرداند.
- `/terms` و `/privacy` باید باز شوند.
- `/tonconnect-manifest.json` باید پس از فعال شدن دامنه، JSON معتبر بدهد.
- در تلگرام به `@AntiScamGuardianSafe2026Bot` برو و `/start` را بفرست.
- دکمه Mini App را باز کن و یک URL آزمایشی و یک آدرس TON معتبر/نامعتبر را تست کن.
- نتیجه و لاگ‌های bot و api را بررسی کن.

## هزینه و محدودیت میزبانی

Railway طرح آزمایشی و طرح Hobby دارد. در زمان تهیه این راهنما، Hobby حداقل پرداخت ماهانه ۵ دلار دارد که ۵ دلار اعتبار مصرف منابع در همان ماه را شامل می‌شود؛ مصرف بیشتر، هزینه اضافه دارد. مبلغ واقعی به RAM، CPU، ترافیک و فضای Volume بستگی دارد. برای پلن پولی ممکن است کارت بانکی معتبر لازم باشد. قبل از ثبت کارت یا ارتقا، صفحه قیمت فعلی Railway را بخوان: https://railway.com/pricing

## پرداخت و عرضه تجاری

فعلاً `PAYMENTS_MODE=disabled` را نگه دار. برای فروش اشتراک دیجیتال داخل تلگرام، روش پرداخت Telegram Stars (XTR) لازم است؛ دریافت مستقیم TON برای بازکردن دسترسی دیجیتال داخل Mini App را فعال نکن. تبدیل/برداشت پاداش Stars به Toncoin نیز به صلاحیت حساب و محدودیت‌های تلگرام وابسته است و تضمین‌شده نیست.

پیش از عرضه عمومی باید:
- هویت مالک محصول، اطلاعات تماس، شرایط خدمات و حریم خصوصی تکمیل و از نظر حقوقی بررسی شوند.
- پوشش داده‌های تهدید، کیفیت نتایج و false positive / false negative ارزیابی شود.
- تست کامل Stars، تمدید، انقضا و refund در محیط تست انجام شود.
- محدودیت‌های کشورهای هدف، قوانین حفاظت داده و شرایط سرویس‌های داده بررسی شوند.
- یک ارزیابی امنیتی مستقل انجام شود.

**توجه:** اسکن، تضمین امنیت نیست. گزارش‌ها صرفاً نشانه‌های ریسک را خلاصه می‌کنند و جای ممیزی قرارداد هوشمند یا بررسی تخصصی تراکنش را نمی‌گیرند.
