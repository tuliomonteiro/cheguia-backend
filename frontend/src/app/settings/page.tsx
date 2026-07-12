"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useMessages, type Lang } from "@/lib/i18n";

export default function SettingsPage() {
  const { user, accessToken, loading, updateProfile } = useAuth();
  const router = useRouter();
  const t = useMessages(user?.language_preference);

  const [languageNotice, setLanguageNotice] = useState(false);
  const [savingLanguage, setSavingLanguage] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newPassword2, setNewPassword2] = useState("");
  const [passwordNotice, setPasswordNotice] = useState<
    { kind: "ok" | "error"; text: string } | null
  >(null);
  const [savingPassword, setSavingPassword] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  async function handleLanguageChange(lang: Lang) {
    setLanguageNotice(false);
    setSavingLanguage(true);
    try {
      await updateProfile({ language_preference: lang });
      setLanguageNotice(true);
    } finally {
      setSavingLanguage(false);
    }
  }

  async function handlePasswordSubmit(e: FormEvent) {
    e.preventDefault();
    if (!accessToken) return;
    setPasswordNotice(null);
    setSavingPassword(true);
    try {
      await api.changePassword(accessToken, {
        current_password: currentPassword,
        new_password: newPassword,
        new_password2: newPassword2,
      });
      setPasswordNotice({ kind: "ok", text: t.passwordChanged });
      setCurrentPassword("");
      setNewPassword("");
      setNewPassword2("");
    } catch (err) {
      setPasswordNotice({
        kind: "error",
        text: err instanceof ApiError ? err.message : t.passwordChangeFailed,
      });
    } finally {
      setSavingPassword(false);
    }
  }

  if (loading || !user) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-zinc-500">
        {t.loading}
      </div>
    );
  }

  const inputClass =
    "mb-4 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-50";
  const labelClass = "mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300";

  return (
    <div className="flex flex-1 justify-center bg-zinc-50 px-4 py-10 dark:bg-black">
      <div className="w-full max-w-md">
        <Link
          href="/"
          className="mb-6 inline-block text-sm text-zinc-600 underline dark:text-zinc-400"
        >
          {t.backToChat}
        </Link>

        <h1 className="mb-6 text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
          {t.settings}
        </h1>

        <section className="mb-8 rounded-xl border border-black/10 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-zinc-900">
          <p className="mb-4 text-sm text-zinc-600 dark:text-zinc-400">{user.email}</p>

          <label className={labelClass}>{t.languageLabel}</label>
          <select
            value={user.language_preference}
            disabled={savingLanguage}
            onChange={(e) => handleLanguageChange(e.target.value as Lang)}
            className={inputClass}
          >
            <option value="pt">{t.portuguese}</option>
            <option value="es">{t.spanish}</option>
          </select>
          {languageNotice && (
            <p className="text-sm text-green-700 dark:text-green-400">{t.languageSaved}</p>
          )}
        </section>

        <section className="rounded-xl border border-black/10 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-zinc-900">
          <h2 className="mb-4 text-lg font-semibold text-zinc-900 dark:text-zinc-50">
            {t.changePasswordTitle}
          </h2>

          <form onSubmit={handlePasswordSubmit}>
            <label className={labelClass}>{t.currentPassword}</label>
            <input
              type="password"
              required
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className={inputClass}
            />

            <label className={labelClass}>{t.newPassword}</label>
            <input
              type="password"
              required
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className={inputClass}
            />

            <label className={labelClass}>{t.confirmNewPassword}</label>
            <input
              type="password"
              required
              value={newPassword2}
              onChange={(e) => setNewPassword2(e.target.value)}
              className={inputClass}
            />

            {passwordNotice && (
              <p
                className={`mb-4 text-sm ${
                  passwordNotice.kind === "ok"
                    ? "text-green-700 dark:text-green-400"
                    : "text-red-600 dark:text-red-400"
                }`}
              >
                {passwordNotice.text}
              </p>
            )}

            <button
              type="submit"
              disabled={savingPassword}
              className="w-full rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-300"
            >
              {savingPassword ? t.saving : t.save}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}
