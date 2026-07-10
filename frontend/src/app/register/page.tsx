"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useLang, useMessages, type Lang } from "@/lib/i18n";

export default function RegisterPage() {
  const { register, user, loading } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  // Browser language pre-selects the dropdown until the user picks one.
  const detectedLang = useLang();
  const [chosenLang, setChosenLang] = useState<Lang | null>(null);
  const language = chosenLang ?? detectedLang;
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const t = useMessages(language);

  useEffect(() => {
    if (!loading && user) router.replace("/");
  }, [loading, user, router]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register({ email, username, password, password2, language_preference: language });
      router.replace("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.registerFailed);
    } finally {
      setSubmitting(false);
    }
  }

  const inputClass =
    "mb-4 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-50";
  const labelClass = "mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300";

  return (
    <div className="flex flex-1 items-center justify-center bg-zinc-50 px-4 dark:bg-black">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-xl border border-black/10 bg-white p-8 shadow-sm dark:border-white/10 dark:bg-zinc-900"
      >
        <h1 className="mb-6 text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
          {t.registerTitle}
        </h1>

        <label className={labelClass}>{t.email}</label>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className={inputClass}
        />

        <label className={labelClass}>{t.username}</label>
        <input
          type="text"
          required
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className={inputClass}
        />

        <label className={labelClass}>{t.languageLabel}</label>
        <select
          value={language}
          onChange={(e) => setChosenLang(e.target.value as Lang)}
          className={inputClass}
        >
          <option value="pt">{t.portuguese}</option>
          <option value="es">{t.spanish}</option>
        </select>

        <label className={labelClass}>{t.password}</label>
        <input
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className={inputClass}
        />

        <label className={labelClass}>{t.confirmPassword}</label>
        <input
          type="password"
          required
          value={password2}
          onChange={(e) => setPassword2(e.target.value)}
          className={inputClass}
        />

        {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          {submitting ? t.creatingAccount : t.createAccount}
        </button>

        <p className="mt-4 text-center text-sm text-zinc-600 dark:text-zinc-400">
          {t.haveAccount}{" "}
          <Link href="/login" className="font-medium underline">
            {t.signInLink}
          </Link>
        </p>
      </form>
    </div>
  );
}
