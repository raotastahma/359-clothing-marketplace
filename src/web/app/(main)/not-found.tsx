import Link from "next/link";

export default function MainNotFound() {
  return (
    <section className="mx-auto max-w-7xl px-6 py-20">
      <h1 className="text-3xl tracking-tight">Страница не найдена</h1>
      <p className="mt-4 text-black/60">Проверьте адрес или вернитесь на главную страницу.</p>
      <Link href="/" className="mt-6 inline-block text-sm underline underline-offset-4">
        На главную
      </Link>
    </section>
  );
}
