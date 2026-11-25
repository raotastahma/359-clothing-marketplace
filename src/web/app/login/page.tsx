"use client";

import { ArrowLeft, Check } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ClipboardEvent, KeyboardEvent } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { useUser } from "@/src/components/providers/user-context";
import {
  ApiError,
  getValidationErrorMessages,
  requestJson,
  setAuthTokens,
  type SendCodeApiResponse,
  type User as ApiUser,
  type VerifyCodeApiResponse,
} from "@/src/lib/api";

const OTP_LENGTH = 4;
const RESEND_SECONDS = 60;

type Step = "phone" | "otp" | "name" | "done";

function formatPhone(digits: string): string {
  if (!digits) return "";

  let result = "";
  if (digits.length > 0) result += `(${digits.slice(0, 3)}`;
  if (digits.length >= 3) result += `) ${digits.slice(3, 6)}`;
  if (digits.length >= 6) result += `-${digits.slice(6, 8)}`;
  if (digits.length >= 8) result += `-${digits.slice(8, 10)}`;

  return result;
}

function emptyOtp(): string[] {
  return Array<string>(OTP_LENGTH).fill("");
}

function formatDisplayPhone(phone: string): string {
  const digits = phone.replace(/\D/g, "").replace(/^7/, "").slice(0, 10);
  return `+7 ${formatPhone(digits)}`;
}

function errorMessage(error: unknown, fallback: string): string {
  const validationMessages = getValidationErrorMessages(error);
  if (validationMessages[0]) return validationMessages[0];
  if (error instanceof ApiError) return error.message;
  return fallback;
}

function profileName(user: ApiUser): string {
  return user.name?.trim() || "Гость";
}

interface PhoneStepProps {
  onNext: (phone: string) => Promise<void>;
}

function PhoneStep({ onNext }: PhoneStepProps) {
  const [raw, setRaw] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  function handleChange(value: string): void {
    setRaw(value.replace(/\D/g, "").slice(0, 10));
    setError("");
  }

  async function handleSubmit(): Promise<void> {
    if (raw.length < 10) {
      setError("Введите полный номер телефона");
      return;
    }

    setIsSubmitting(true);
    try {
      await onNext(`+7${raw}`);
    } catch (error) {
      setError(errorMessage(error, "Не удалось отправить код"));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-7">
      <div>
        <h1
          className="mb-2 text-black"
          style={{ fontSize: "26px", fontWeight: 400, letterSpacing: "0.3px" }}
        >
          Войти или создать аккаунт
        </h1>
        <p className="text-[13px] leading-relaxed text-black/50">
          Введите номер телефона — отправим код подтверждения
        </p>
      </div>

      <div className="space-y-2">
        <div className="relative flex items-center border border-black/20 transition-colors focus-within:border-black">
          <span className="shrink-0 select-none pr-2 pl-4 text-sm text-black/50">+7</span>
          <div className="h-5 w-px shrink-0 bg-black/15" />
          <input
            type="tel"
            inputMode="numeric"
            value={formatPhone(raw)}
            onChange={(event) => handleChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void handleSubmit();
            }}
            placeholder="(___) ___-__-__"
            autoFocus
            className="flex-1 bg-transparent py-4 pr-4 pl-3 text-sm placeholder:text-black/25 focus:outline-none"
          />
        </div>
        {error ? <p className="text-[12px] text-red-500">{error}</p> : null}
      </div>

      <button
        type="button"
        onClick={() => void handleSubmit()}
        disabled={isSubmitting}
        className="w-full bg-black py-4 text-[12px] tracking-[2px] text-white uppercase transition-colors hover:bg-black/80 disabled:cursor-not-allowed disabled:bg-black/40"
      >
        {isSubmitting ? "Отправляем..." : "Получить код"}
      </button>

      <p className="text-center text-[11px] leading-relaxed text-black/35">
        Продолжая, вы соглашаетесь с{" "}
        <a href="#" className="underline underline-offset-2 transition-colors hover:text-black">
          условиями использования
        </a>{" "}
        и{" "}
        <a href="#" className="underline underline-offset-2 transition-colors hover:text-black">
          политикой обработки персональных данных
        </a>
      </p>
    </div>
  );
}

interface OtpStepProps {
  phone: string;
  onNext: (code: string) => Promise<void>;
  onBack: () => void;
  onResend: () => Promise<void>;
}

function OtpStep({ phone, onNext, onBack, onResend }: OtpStepProps) {
  const [digits, setDigits] = useState<string[]>(emptyOtp);
  const [error, setError] = useState<string>("");
  const [timer, setTimer] = useState<number>(RESEND_SECONDS);
  const [resent, setResent] = useState<boolean>(false);
  const [isVerifying, setIsVerifying] = useState<boolean>(false);
  const [isResending, setIsResending] = useState<boolean>(false);
  const refs = useRef<Array<HTMLInputElement | null>>([]);

  useEffect(() => {
    if (timer <= 0) return undefined;

    const id = window.setTimeout(() => setTimer((value) => value - 1), 1000);
    return () => window.clearTimeout(id);
  }, [timer]);

  const verify = useCallback(
    async (code: string): Promise<void> => {
      if (isVerifying) return;

      setIsVerifying(true);
      try {
        await onNext(code);
      } catch (error) {
        setError(errorMessage(error, "Неверный код. Попробуйте снова"));
        setDigits(emptyOtp());
        window.setTimeout(() => refs.current[0]?.focus(), 0);
      } finally {
        setIsVerifying(false);
      }
    },
    [isVerifying, onNext],
  );

  function handleInput(index: number, value: string): void {
    const char = value.replace(/\D/g, "").slice(-1);
    const next = [...digits];
    next[index] = char;

    setDigits(next);
    setError("");

    if (char && index < OTP_LENGTH - 1) refs.current[index + 1]?.focus();
    if (char && next.every((digit) => digit !== "")) void verify(next.join(""));
  }

  function handleKeyDown(index: number, event: KeyboardEvent<HTMLInputElement>): void {
    if (event.key === "Backspace" && !digits[index] && index > 0) {
      refs.current[index - 1]?.focus();
    }
  }

  function handlePaste(event: ClipboardEvent<HTMLDivElement>): void {
    const pasted = event.clipboardData.getData("text").replace(/\D/g, "").slice(0, OTP_LENGTH);
    if (!pasted) return;

    event.preventDefault();
    const next = emptyOtp();
    pasted.split("").forEach((char, index) => {
      next[index] = char;
    });

    setDigits(next);
    refs.current[Math.min(pasted.length, OTP_LENGTH - 1)]?.focus();
    if (pasted.length === OTP_LENGTH) void verify(pasted);
  }

  async function handleResend(): Promise<void> {
    setIsResending(true);
    try {
      await onResend();
      setTimer(RESEND_SECONDS);
      setResent(true);
      setDigits(emptyOtp());
      setError("");
      refs.current[0]?.focus();
      window.setTimeout(() => setResent(false), 3000);
    } catch (error) {
      setError(errorMessage(error, "Не удалось отправить код повторно"));
    } finally {
      setIsResending(false);
    }
  }

  const isComplete = digits.every((digit) => digit !== "");

  return (
    <div className="flex flex-col gap-6">
      <div>
        <button
          type="button"
          onClick={onBack}
          className="-ml-0.5 mb-5 flex items-center gap-1.5 text-[12px] text-black/40 transition-colors hover:text-black"
        >
          <ArrowLeft size={14} />
          Назад
        </button>
        <h1
          className="mb-1 text-black"
          style={{ fontSize: "26px", fontWeight: 400, letterSpacing: "0.3px" }}
        >
          Введите код
        </h1>
        <p className="text-[13px] text-black/50">
          Отправили SMS на <span className="text-black">{formatDisplayPhone(phone)}</span>
        </p>
      </div>

      <div className="flex gap-3" onPaste={handlePaste}>
        {digits.map((digit, index) => (
          <input
            key={index}
            ref={(element) => {
              refs.current[index] = element;
            }}
            type="text"
            inputMode="numeric"
            maxLength={1}
            value={digit}
            onChange={(event) => handleInput(index, event.target.value)}
            onKeyDown={(event) => handleKeyDown(index, event)}
            autoFocus={index === 0}
            className={`h-14 w-14 shrink-0 border text-center text-xl transition-colors focus:outline-none ${
              error
                ? "border-red-400 bg-red-50"
                : digit
                  ? "border-black bg-black/5"
                  : "border-black/20 focus:border-black"
            }`}
          />
        ))}
      </div>

      {error ? <p className="-mt-2 text-[12px] text-red-500">{error}</p> : null}

      <div className="text-center">
        {resent ? (
          <p className="text-[12px] text-black/50">Код отправлен повторно</p>
        ) : timer > 0 ? (
          <p className="text-[12px] text-black/40">
            Повторная отправка через{" "}
            <span className="tabular-nums text-black">
              {Math.floor(timer / 60)}:{String(timer % 60).padStart(2, "0")}
            </span>
          </p>
        ) : (
          <button
            type="button"
            onClick={() => void handleResend()}
            disabled={isResending}
            className="text-[12px] text-black underline underline-offset-2 transition-colors hover:text-black/60"
          >
            {isResending ? "Отправляем..." : "Отправить код повторно"}
          </button>
        )}
      </div>

      <button
        type="button"
        onClick={() => void verify(digits.join(""))}
        disabled={!isComplete || isVerifying}
        className={`w-full py-4 text-[12px] tracking-[2px] uppercase transition-colors ${
          isComplete && !isVerifying
            ? "bg-black text-white hover:bg-black/80"
            : "cursor-not-allowed bg-black/10 text-black/30"
        }`}
      >
        {isVerifying ? "Проверяем..." : "Подтвердить"}
      </button>
    </div>
  );
}

interface NameStepProps {
  onNext: (name: string, pdConsent: boolean, marketingConsent: boolean) => Promise<void>;
}

function NameStep({ onNext }: NameStepProps) {
  const [name, setName] = useState<string>("");
  const [touched, setTouched] = useState<boolean>(false);
  const [pdConsent, setPdConsent] = useState<boolean>(false);
  const [marketingConsent, setMarketingConsent] = useState<boolean>(false);
  const [pdError, setPdError] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const hasError = touched && name.trim().length < 2;

  async function handleContinue(): Promise<void> {
    setTouched(true);
    setSubmitError("");
    if (name.trim().length < 2) return;
    if (!pdConsent) {
      setPdError(true);
      return;
    }
    setIsSubmitting(true);
    try {
      await onNext(name.trim(), pdConsent, marketingConsent);
    } catch (error) {
      setSubmitError(errorMessage(error, "Не удалось сохранить имя"));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-7">
      <div>
        <h1
          className="mb-2 text-black"
          style={{ fontSize: "26px", fontWeight: 400, letterSpacing: "0.3px" }}
        >
          Как вас зовут?
        </h1>
        <p className="text-[13px] text-black/50">Завершите создание аккаунта</p>
      </div>

      <div className="space-y-2">
        <input
          type="text"
          value={name}
          onChange={(event) => {
            setName(event.target.value);
            setTouched(false);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") void handleContinue();
          }}
          placeholder="Имя Фамилия"
          autoFocus
          className={`w-full border px-4 py-4 text-sm transition-colors focus:outline-none ${
            hasError ? "border-red-400" : "border-black/20 focus:border-black"
          }`}
        />
        {hasError ? <p className="text-[12px] text-red-500">Введите ваше имя</p> : null}
      </div>

      <div className="space-y-3 border-t border-black/10 pt-5">
        <div
          className="group flex cursor-pointer items-start gap-3"
          onClick={() => setMarketingConsent((value) => !value)}
        >
          <div
            className={`mt-0.5 h-4 w-4 shrink-0 border transition-colors ${
              marketingConsent
                ? "border-black bg-black"
                : "border-black/30 group-hover:border-black/60"
            }`}
          />
          <span className="select-none text-[12px] leading-relaxed text-black/60">
            Согласен на получение рекламно-информационных материалов
          </span>
        </div>

        <div
          className="group flex cursor-pointer items-start gap-3"
          onClick={() => {
            setPdConsent((value) => !value);
            setPdError(false);
          }}
        >
          <div
            className={`mt-0.5 h-4 w-4 shrink-0 border transition-colors ${
              pdConsent
                ? "border-black bg-black"
                : pdError
                  ? "border-red-500"
                  : "border-black/30 group-hover:border-black/60"
            }`}
          />
          <span className="select-none text-[12px] leading-relaxed text-black/60">
            Согласен на обработку персональных данных <span className="text-black">*</span>
          </span>
        </div>
        {pdError ? (
          <p className="ml-7 text-[11px] text-red-500">
            Необходимо принять условия для продолжения
          </p>
        ) : null}
      </div>

      <button
        type="button"
        onClick={() => void handleContinue()}
        disabled={isSubmitting}
        className="w-full bg-black py-4 text-[12px] tracking-[2px] text-white uppercase transition-colors hover:bg-black/80 disabled:cursor-not-allowed disabled:bg-black/40"
      >
        {isSubmitting ? "Сохраняем..." : "Продолжить"}
      </button>
      {submitError ? <p className="-mt-4 text-center text-[12px] text-red-500">{submitError}</p> : null}

    </div>
  );
}

function DoneStep({ name }: { name: string }) {
  const router = useRouter();

  useEffect(() => {
    const id = window.setTimeout(() => router.push("/profile"), 1800);
    return () => window.clearTimeout(id);
  }, [router]);

  return (
    <div className="flex flex-col items-center gap-5 py-10">
      <div className="flex h-16 w-16 items-center justify-center bg-black">
        <Check size={28} className="text-white" strokeWidth={1.5} />
      </div>
      <div className="text-center">
        <h2 className="mb-1 text-black" style={{ fontSize: "22px", fontWeight: 400 }}>
          Добро пожаловать, {name}!
        </h2>
        <p className="text-[13px] text-black/50">Переходим в профиль…</p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const { login, user } = useUser();
  const [step, setStep] = useState<Step>("phone");
  const [phone, setPhone] = useState<string>("");
  const [userName, setUserName] = useState<string>("");
  const [pendingUser, setPendingUser] = useState<ApiUser | null>(null);

  useEffect(() => {
    if (user && step !== "done") router.replace("/profile");
  }, [router, step, user]);

  const finishLogin = useCallback(
    (nextUser: ApiUser, pdConsent: boolean, marketingConsent: boolean): void => {
      const name = profileName(nextUser);
      setUserName(name);
      login({
        id: nextUser.id,
        phone: nextUser.phone,
        name,
        email: nextUser.email,
        isVerified: nextUser.is_verified,
        pdConsent,
        marketingConsent,
      });
      setStep("done");
    },
    [login],
  );

  async function sendCode(nextPhone: string): Promise<void> {
    await requestJson<SendCodeApiResponse>("/auth/send-code", {
      method: "POST",
      body: { phone: nextPhone },
      redirectOnUnauthorized: false,
    });

    setPhone(nextPhone);
    setStep("otp");
  }

  async function verifyCode(code: string): Promise<void> {
    const { data } = await requestJson<VerifyCodeApiResponse>("/auth/verify-code", {
      method: "POST",
      body: { phone, code },
      redirectOnUnauthorized: false,
      skipAuthRefresh: true,
    });

    setAuthTokens(data);

    if (data.user.name?.trim()) {
      finishLogin(data.user, false, false);
      return;
    }

    setPendingUser(data.user);
    setStep("name");
  }

  async function finishNewUser(
    name: string,
    pdConsent: boolean,
    marketingConsent: boolean,
  ): Promise<void> {
    await requestJson<unknown>("/users/me", {
      method: "PATCH",
      body: { name },
      redirectOnUnauthorized: false,
    });

    const nextUser = pendingUser ?? {
      id: "",
      phone,
      name,
      email: null,
      is_verified: true,
    };
    finishLogin({ ...nextUser, name }, pdConsent, marketingConsent);
  }

  async function finishLoginFromName(
    name: string,
    pdConsent: boolean,
    marketingConsent: boolean,
  ): Promise<void> {
    setUserName(name);
    login({ phone, name, pdConsent, marketingConsent });
    setStep("done");
  }

  if (user && step !== "done") return null;

  return (
    <main className="flex min-h-screen flex-col bg-white">
      <div className="relative flex items-center justify-center border-b border-black/10 px-5 py-4">
        <Link
          href="/"
          className="absolute left-5 flex items-center gap-1.5 text-[11px] tracking-[1.5px] text-black/40 uppercase transition-colors hover:text-black"
        >
          <ArrowLeft size={14} />
          В магазин
        </Link>
        <Link href="/" aria-label="359">
          <Image src="/logo.svg" alt="359" width={74} height={28} className="h-7 w-auto" priority />
        </Link>
      </div>

      <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-10 md:px-0">
        {step === "phone" ? (
          <PhoneStep onNext={sendCode} />
        ) : null}

        {step === "otp" ? (
          <OtpStep
            phone={phone}
            onNext={verifyCode}
            onBack={() => setStep("phone")}
            onResend={() => sendCode(phone)}
          />
        ) : null}

        {step === "name" ? <NameStep onNext={pendingUser ? finishNewUser : finishLoginFromName} /> : null}

        {step === "done" ? <DoneStep name={userName} /> : null}
      </div>
    </main>
  );
}
