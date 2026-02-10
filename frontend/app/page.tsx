"use client";

import Link from "next/link";
import { useWallet } from "@solana/wallet-adapter-react";
import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";

export default function HomePage() {
  const { connected, publicKey } = useWallet();

  return (
    <main className="space-y-6">
      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Connect your wallet</h2>
        <WalletMultiButton className="btn-primary" />
        <p className="text-sm text-slate-300">
          Status:{" "}
          {connected && publicKey
            ? `Connected: ${publicKey.toBase58().slice(0, 4)}...${publicKey
                .toBase58()
                .slice(-4)}`
            : "Not connected"}
        </p>
      </section>

      <section className="space-y-2">
        <h3 className="font-medium">Next steps</h3>
        <ul className="list-disc list-inside text-sm text-slate-300">
          <li>Connect your Phantom wallet</li>
          <li>Go to the subscription page to activate premium</li>
        </ul>
        <Link
          href="/subscribe"
          className="inline-flex mt-2 px-4 py-2 rounded-md bg-emerald-500 text-sm font-medium hover:bg-emerald-600"
        >
          Go to Subscription
        </Link>
      </section>
    </main>
  );
}

