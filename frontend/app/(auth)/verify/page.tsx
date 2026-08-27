"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { apiFetch, ApiError, type UserOut } from "@/lib/api";

type VerifyResponse = { user: UserOut };

function VerifyStatus() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { refresh } = useAuth();
  const token = searchParams.get("token") ?? "";
  const [state, setState] = useState<"working" | "done" | "error">("working");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        await apiFetch<VerifyResponse>("/api/auth/verify", {
          method: "POST",
          body: { token },
        });
        await refresh();
        if (!cancelled) {
          setState("done");
          setTimeout(() => router.push("/play"), 800);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Something went wrong.");
          setState("error");
        }
      }
    }

    if (token) {
      void run();
    } else {
      setState("error");
      setError("That link isn't right.");
    }

    return () => {
      cancelled = true;
    };
  }, [token, router, refresh]);

  return (
    <main className="mx-auto max-w-sm px-4 py-24 text-center">
      {state === "working" && <p className="text-xl">One moment.</p>}
      {state === "done" && <p className="text-xl">You&apos;re in.</p>}
      {state === "error" && <p className="text-xl text-red-600">{error}</p>}
    </main>
  );
}

export default function VerifyPage() {
  return (
    <Suspense fallback={null}>
      <VerifyStatus />
    </Suspense>
  );
}
