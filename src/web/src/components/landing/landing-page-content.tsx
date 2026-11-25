import Image from "next/image";
import Link from "next/link";

const LOOKBOOK_ITEMS = [
  {
    title: "Outerwear edit",
    subtitle: "Технологичные ткани и чистые силуэты",
    image:
      "/demo-product.svg",
  },
  {
    title: "Monochrome essentials",
    subtitle: "Базовые элементы для повседневного гардероба",
    image:
      "/demo-product.svg",
  },
  {
    title: "Weekend tailoring",
    subtitle: "Смарт-капсула для города и путешествий",
    image:
      "/demo-product.svg",
  },
] as const;

const FEATURED_BRANDS = [
  { name: "12 STOREEZ", year: "2014" },
  { name: "USHATAVA", year: "2015" },
  { name: "Gate31", year: "2016" },
  { name: "LIME Studio", year: "2008" },
  { name: "Present & Simple", year: "2016" },
  { name: "1811 Eighteen One One", year: "2011" },
] as const;

const BLOG_POSTS = [
  {
    title: "Как собрать капсульный гардероб на сезон",
    date: "5 марта 2026",
    image:
      "/demo-product.svg",
  },
  {
    title: "5 локальных брендов, за которыми стоит следить",
    date: "1 марта 2026",
    image:
      "/demo-product.svg",
  },
  {
    title: "Тренды материалов: что выбрать этой весной",
    date: "24 февраля 2026",
    image:
      "/demo-product.svg",
  },
] as const;

const CATEGORIES = ["Верхняя одежда", "Трикотаж", "Платья", "Брюки", "Обувь", "Аксессуары"] as const;

function SectionTitle({ title, caption }: { title: string; caption: string }) {
  return (
    <div className="mb-8 flex flex-col gap-2 md:mb-10 md:flex-row md:items-end md:justify-between">
      <h2 className="text-2xl tracking-tight md:text-3xl">{title}</h2>
      <p className="text-sm text-black/50">{caption}</p>
    </div>
  );
}

export function LandingPageContent() {
  return (
    <div className="bg-white text-black">
      <section className="relative min-h-[72vh] overflow-hidden border-b border-black/10 md:min-h-[82vh]">
        <Image
          src="/demo-product.svg"
          alt="Новая коллекция 359"
          fill
          unoptimized
          sizes="100vw"
          className="object-cover"
          priority
        />
        <div className="absolute inset-0 bg-black/35" />
        <div className="relative mx-auto flex min-h-[72vh] max-w-7xl items-end px-6 py-12 md:min-h-[82vh] md:px-10 md:py-16">
          <div className="max-w-xl text-white">
            <p className="mb-4 text-xs tracking-[2.4px] uppercase text-white/80">359 marketplace</p>
            <h1 className="text-4xl tracking-tight md:text-6xl">Новая глава локальной моды</h1>
            <p className="mt-4 max-w-md text-sm text-white/80 md:text-base">
              Коллекции российских дизайнеров в одном пространстве. Ограниченные дропы, новые бренды и
              curated-подборки на каждый день.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/shop"
                className="border border-white bg-white px-5 py-3 text-xs tracking-[1.8px] text-black uppercase transition-opacity hover:opacity-90"
              >
                Перейти в каталог
              </Link>
              <Link
                href="/shop?badge=New"
                className="border border-white/60 px-5 py-3 text-xs tracking-[1.8px] text-white uppercase transition-colors hover:border-white hover:bg-white hover:text-black"
              >
                Смотреть новинки
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-14 md:px-10 md:py-20">
        <SectionTitle title="Lookbook" caption="Образы недели от брендов-партнеров" />
        <div className="grid gap-4 md:grid-cols-3">
          {LOOKBOOK_ITEMS.map((item) => (
            <article key={item.title} className="group border border-black/10">
              <div className="relative aspect-[4/5] overflow-hidden">
                <Image
                  src={item.image}
                  alt={item.title}
                  fill
                  unoptimized
                  sizes="(max-width: 768px) 100vw, 33vw"
                  className="object-cover transition-transform duration-300 group-hover:scale-[1.03]"
                />
              </div>
              <div className="space-y-2 p-4">
                <h3 className="text-lg">{item.title}</h3>
                <p className="text-sm text-black/60">{item.subtitle}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 pb-14 md:px-10 md:pb-20">
        <div className="grid gap-6 border border-black/10 p-6 md:grid-cols-[1.15fr_1fr] md:p-10">
          <div className="space-y-4">
            <p className="text-xs tracking-[2px] text-black/50 uppercase">Campaign</p>
            <h2 className="text-3xl tracking-tight md:text-4xl">Городской минимализм весна-лето 2026</h2>
            <p className="max-w-xl text-sm text-black/60">
              Капсула с фокусом на функциональность: прямые силуэты, натуральные фактуры и оттенки, которые
              легко комбинировать между собой.
            </p>
            <Link
              href="/shop"
              className="inline-flex border border-black px-5 py-3 text-xs tracking-[1.8px] uppercase transition-colors hover:bg-black hover:text-white"
            >
              Смотреть кампанию
            </Link>
          </div>
          <div className="relative aspect-[4/3] overflow-hidden">
            <Image
              src="/demo-product.svg"
              alt="Кампейн новой коллекции"
              fill
              unoptimized
              sizes="(max-width: 768px) 100vw, 42vw"
              className="object-cover"
            />
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-6 pb-14 md:grid-cols-2 md:px-10 md:pb-20">
        <article className="relative min-h-72 overflow-hidden border border-black/10 p-6 md:p-8">
          <Image
            src="/demo-product.svg"
            alt="Промо со скидками"
            fill
            unoptimized
            sizes="(max-width: 768px) 100vw, 50vw"
            className="object-cover"
          />
          <div className="absolute inset-0 bg-black/30" />
          <div className="relative flex h-full flex-col justify-end text-white">
            <p className="text-xs tracking-[2px] uppercase text-white/80">Dual Promo</p>
            <h3 className="mt-2 text-2xl tracking-tight">Selected Sale до -40%</h3>
            <Link
              href="/shop?badge=Sale"
              className="mt-5 inline-flex w-fit border border-white px-4 py-2 text-xs tracking-[1.6px] uppercase transition-colors hover:bg-white hover:text-black"
            >
              Перейти к sale
            </Link>
          </div>
        </article>

        <article className="relative min-h-72 overflow-hidden border border-black/10 p-6 md:p-8">
          <Image
            src="/demo-product.svg"
            alt="Новый дроп брендов"
            fill
            unoptimized
            sizes="(max-width: 768px) 100vw, 50vw"
            className="object-cover"
          />
          <div className="absolute inset-0 bg-black/30" />
          <div className="relative flex h-full flex-col justify-end text-white">
            <p className="text-xs tracking-[2px] uppercase text-white/80">New Drop</p>
            <h3 className="mt-2 text-2xl tracking-tight">Дроп недели: лимитированная серия</h3>
            <Link
              href="/shop?badge=New"
              className="mt-5 inline-flex w-fit border border-white px-4 py-2 text-xs tracking-[1.6px] uppercase transition-colors hover:bg-white hover:text-black"
            >
              Смотреть новинки
            </Link>
          </div>
        </article>
      </section>

      <section className="mx-auto max-w-7xl px-6 pb-14 md:px-10 md:pb-20">
        <SectionTitle title="Бренды 359" caption="Established и emerging бренды на одной платформе" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURED_BRANDS.map((brand) => (
            <Link
              key={brand.name}
              href="/shop"
              className="group flex items-center justify-between border border-black/10 px-4 py-4 transition-colors hover:border-black"
            >
              <div>
                <p className="text-base tracking-tight">{brand.name}</p>
                <p className="text-xs text-black/50">Основан в {brand.year}</p>
              </div>
              <span className="text-xs tracking-[1.6px] text-black/40 uppercase transition-colors group-hover:text-black">
                Смотреть
              </span>
            </Link>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 pb-14 md:px-10 md:pb-20">
        <SectionTitle title="Из блога" caption="Редакционные материалы и бренд-истории" />
        <div className="grid gap-5 md:grid-cols-3">
          {BLOG_POSTS.map((post) => (
            <article key={post.title} className="border border-black/10">
              <div className="relative aspect-[3/2] overflow-hidden">
                <Image
                  src={post.image}
                  alt={post.title}
                  fill
                  unoptimized
                  sizes="(max-width: 768px) 100vw, 33vw"
                  className="object-cover"
                />
              </div>
              <div className="space-y-2 p-4">
                <p className="text-xs tracking-[1.4px] text-black/50 uppercase">{post.date}</p>
                <h3 className="text-lg leading-snug">{post.title}</h3>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-black/10 bg-[#f5f5f5]">
        <div className="mx-auto grid max-w-7xl gap-8 px-6 py-14 md:grid-cols-[1.3fr_1fr] md:items-center md:px-10 md:py-20">
          <div>
            <p className="text-xs tracking-[2px] text-black/50 uppercase">App Download</p>
            <h2 className="mt-3 text-3xl tracking-tight md:text-4xl">Мобильное приложение скоро</h2>
            <p className="mt-4 max-w-xl text-sm text-black/60">
              Добавляйте товары в избранное, отслеживайте заказы и получайте уведомления о новых дропах.
              Раздел оставлен как заглушка для MVP.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <button
                type="button"
                className="border border-black/20 bg-white px-5 py-3 text-xs tracking-[1.6px] text-black/40 uppercase"
                disabled
              >
                App Store — скоро
              </button>
              <button
                type="button"
                className="border border-black/20 bg-white px-5 py-3 text-xs tracking-[1.6px] text-black/40 uppercase"
                disabled
              >
                Google Play — скоро
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {CATEGORIES.map((category) => (
              <Link
                key={category}
                href="/shop"
                className="border border-black/10 bg-white px-4 py-5 text-sm transition-colors hover:border-black"
              >
                {category}
              </Link>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
