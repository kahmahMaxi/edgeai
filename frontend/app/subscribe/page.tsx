"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useConnection, useWallet } from "@solana/wallet-adapter-react";
import { pollSubscriptionPda, sendSubscribeSolTx } from "../../lib/solana";

const solEnabled =
  (process.env.NEXT_PUBLIC_SUBSCRIBE_SOL_ENABLED ?? "true").toLowerCase() === "true";
const solAmount = Number(process.env.NEXT_PUBLIC_SUBSCRIBE_SOL_AMOUNT ?? "0.01");
const usdcEnabled =
  (process.env.NEXT_PUBLIC_SUBSCRIBE_USDC_ENABLED ?? "true").toLowerCase() === "true";
const usdcAmount = Number(process.env.NEXT_PUBLIC_SUBSCRIBE_USDC_AMOUNT ?? "3");

export default function SubscribePage() {
  const { connection } = useConnection();
  const wallet = useWallet();

  const [status, setStatus] = useState<string>("");
  const [txSig, setTxSig] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [subActive, setSubActive] = useState<boolean | null>(null);

  useEffect(() => {
    if (!wallet.connected) {
      setStatus("Connect your wallet to subscribe.");
      setSubActive(null);
    }
  }, [wallet.connected]);

  const handleSubscribeSol = async () => {
    if (!wallet.connected || !wallet.publicKey) {
      setStatus("Please connect your wallet first.");
      return;
    }

    try {
      setIsLoading(true);
      setStatus("Sending subscribe_sol transaction...");
      const sig = await sendSubscribeSolTx(connection, wallet);
      setTxSig(sig);
      setStatus("Transaction sent. Waiting for subscription PDA to activate...");

      const active = await pollSubscriptionPda(connection, wallet.publicKey, 120_000, 3_000);
      setSubActive(active);
      setStatus(
        active
          ? "Subscription active! 🎉"
          : "Subscription not detected yet. Check later or try again."
      );
    } catch (e: any) {
      console.error(e);
      setStatus(`Error: ${e.message ?? "Failed to subscribe."}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="space-y-6">
      <Link href="/" className="text-sm text-emerald-400 hover:underline">
        ← Back
      </Link>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Subscribe to $EDGEAI Premium</h2>
        <p className="text-sm text-slate-300">
          Connected wallet:{" "}
          {wallet.connected && wallet.publicKey
            ? `${wallet.publicKey.toBase58().slice(0, 4)}...${wallet.publicKey
                .toBase58()
                .slice(-4)}`
            : "Not connected"}
        </p>
      </section>

      {!wallet.connected && (
        <p className="text-sm text-red-400">Please go back and connect your wallet first.</p>
      )}

      {wallet.connected && (
        <section className="space-y-3">
          <p className="text-sm text-slate-200">Choose a payment method:</p>
          <div className="flex gap-3 flex-wrap">
            {solEnabled && (
              <button
                onClick={handleSubscribeSol}
                disabled={isLoading}
                className="px-4 py-2 rounded-md bg-emerald-500 text-sm font-medium hover:bg-emerald-600 disabled:opacity-60"
              >
                {isLoading ? "Subscribing..." : `Subscribe with ${solAmount} SOL`}
              </button>
            )}
            {usdcEnabled && (
              <button
                disabled
                className="px-4 py-2 rounded-md bg-slate-700 text-sm font-medium opacity-60 cursor-not-allowed"
              >
                Subscribe with {usdcAmount} USDC (coming soon)
              </button>
            )}
            {!solEnabled && !usdcEnabled && (
              <p className="text-sm text-yellow-400">
                Subscription temporarily disabled. Please check back later.
              </p>
            )}
          </div>
        </section>
      )}

      <section className="space-y-2">
        <p className="text-sm text-slate-200">Status:</p>
        <p className="text-sm text-slate-300 whitespace-pre-line">
          {status || "Idle."}
        </p>
        {typeof subActive === "boolean" && (
          <p className="text-sm">
            Subscription PDA status:{" "}
            <span className={subActive ? "text-emerald-400" : "text-red-400"}>
              {subActive ? "ACTIVE" : "NOT ACTIVE"}
            </span>
          </p>
        )}
        {txSig && (
          <p className="text-sm">
            Tx:{" "}
            <a
              href={`https://explorer.solana.com/tx/${txSig}?cluster=devnet`}
              target="_blank"
              rel="noreferrer"
              className="text-emerald-400 hover:underline"
            >
              View on Solana Explorer
            </a>
          </p>
        )}
      </section>
    </main>
  );
}

