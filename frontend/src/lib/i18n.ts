"use client";

import { useSyncExternalStore } from "react";

export type Lang = "pt" | "es";

export interface Messages {
  // chat
  signOut: string;
  newChat: string;
  untitledChat: string;
  emptyPrompt: string;
  sources: string;
  inputPlaceholder: string;
  send: string;
  sending: string;
  sendFailed: string;
  loading: string;
  deleteChat: string;
  deleteConfirm: string;
  deleteFailed: string;
  // login
  loginTitle: string;
  email: string;
  password: string;
  signIn: string;
  signingIn: string;
  loginFailed: string;
  noAccount: string;
  registerLink: string;
  // register
  registerTitle: string;
  username: string;
  confirmPassword: string;
  languageLabel: string;
  portuguese: string;
  spanish: string;
  createAccount: string;
  creatingAccount: string;
  registerFailed: string;
  haveAccount: string;
  signInLink: string;
}

const MESSAGES: Record<Lang, Messages> = {
  pt: {
    signOut: "Sair",
    newChat: "+ Nova conversa",
    untitledChat: "Conversa sem título",
    emptyPrompt: "Pergunte sobre imigração, impostos, ANDE ou bancos no Paraguai.",
    sources: "Fontes:",
    inputPlaceholder: "Digite sua pergunta…",
    send: "Enviar",
    sending: "Enviando…",
    sendFailed: "Não foi possível enviar a mensagem.",
    loading: "Carregando…",
    deleteChat: "Apagar conversa",
    deleteConfirm: "Apagar esta conversa? Esta ação não pode ser desfeita.",
    deleteFailed: "Não foi possível apagar a conversa.",
    loginTitle: "Entrar na Cheguia",
    email: "E-mail",
    password: "Senha",
    signIn: "Entrar",
    signingIn: "Entrando…",
    loginFailed: "Não foi possível entrar.",
    noAccount: "Não tem conta?",
    registerLink: "Cadastre-se",
    registerTitle: "Crie sua conta Cheguia",
    username: "Nome de usuário",
    confirmPassword: "Confirme a senha",
    languageLabel: "Idioma",
    portuguese: "Português",
    spanish: "Espanhol",
    createAccount: "Criar conta",
    creatingAccount: "Criando conta…",
    registerFailed: "Não foi possível criar a conta.",
    haveAccount: "Já tem uma conta?",
    signInLink: "Entrar",
  },
  es: {
    signOut: "Salir",
    newChat: "+ Nueva conversación",
    untitledChat: "Conversación sin título",
    emptyPrompt: "Preguntá sobre migraciones, impuestos, ANDE o bancos en Paraguay.",
    sources: "Fuentes:",
    inputPlaceholder: "Escribí tu pregunta…",
    send: "Enviar",
    sending: "Enviando…",
    sendFailed: "No se pudo enviar el mensaje.",
    loading: "Cargando…",
    deleteChat: "Eliminar conversación",
    deleteConfirm: "¿Eliminar esta conversación? Esta acción no se puede deshacer.",
    deleteFailed: "No se pudo eliminar la conversación.",
    loginTitle: "Iniciar sesión en Cheguia",
    email: "Correo electrónico",
    password: "Contraseña",
    signIn: "Iniciar sesión",
    signingIn: "Iniciando sesión…",
    loginFailed: "No se pudo iniciar sesión.",
    noAccount: "¿No tenés cuenta?",
    registerLink: "Registrate",
    registerTitle: "Creá tu cuenta Cheguia",
    username: "Nombre de usuario",
    confirmPassword: "Confirmá la contraseña",
    languageLabel: "Idioma",
    portuguese: "Portugués",
    spanish: "Español",
    createAccount: "Crear cuenta",
    creatingAccount: "Creando cuenta…",
    registerFailed: "No se pudo crear la cuenta.",
    haveAccount: "¿Ya tenés cuenta?",
    signInLink: "Iniciar sesión",
  },
};

/**
 * Resolve the UI language: an explicit preference ("pt"/"es", e.g. the
 * logged-in user's language_preference) wins; otherwise the browser
 * language; Spanish is the fallback, matching the backend default.
 */
export function resolveLang(pref?: string): Lang {
  if (pref === "pt" || pref === "es") return pref;
  if (typeof navigator !== "undefined" && navigator.language?.toLowerCase().startsWith("pt")) {
    return "pt";
  }
  return "es";
}

const subscribeNever = () => () => {};

/**
 * Current UI language, hydration-safe: pages are statically prerendered
 * without a navigator, so the server snapshot is the preference (or the
 * Spanish fallback) and browser detection kicks in on the client.
 */
export function useLang(pref?: string): Lang {
  return useSyncExternalStore(
    subscribeNever,
    () => resolveLang(pref),
    () => (pref === "pt" || pref === "es" ? pref : "es"),
  );
}

/** Messages for the current language (see useLang). */
export function useMessages(pref?: string): Messages {
  return MESSAGES[useLang(pref)];
}
