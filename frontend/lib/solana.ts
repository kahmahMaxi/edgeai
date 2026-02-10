"use client";

import { Connection, PublicKey, SystemProgram, Transaction, TransactionInstruction } from "@solana/web3.js";
import type { WalletContextState } from "@solana/wallet-adapter-react";

const PROGRAM_ID = new PublicKey(process.env.NEXT_PUBLIC_PROGRAM_ID!);
const SUBSCRIPTION_SEED = Buffer.from("subscription");

export function getSubscriptionPda(user: PublicKey): PublicKey {
  const [pda] = PublicKey.findProgramAddressSync(
    [SUBSCRIPTION_SEED, user.toBuffer()],
    PROGRAM_ID
  );
  return pda;
}

async function getIxDiscriminator(name: string): Promise<Buffer> {
  // Anchor: first 8 bytes of sha256("global:<name>")
  const preimage = new TextEncoder().encode(`global:${name}`);
  const hashBuf = await crypto.subtle.digest("SHA-256", preimage);
  return Buffer.from(hashBuf).subarray(0, 8);
}

export async function buildSubscribeSolIx(
  user: PublicKey
): Promise<TransactionInstruction> {
  // Config PDA: seeds = ["config"]
  const [configPda] = PublicKey.findProgramAddressSync(
    [Buffer.from("config")],
    PROGRAM_ID
  );

  const subscriptionPda = getSubscriptionPda(user);
  const feeWalletStr = process.env.NEXT_PUBLIC_FEE_WALLET;
  if (!feeWalletStr) {
    throw new Error("NEXT_PUBLIC_FEE_WALLET not set");
  }
  const feeWallet = new PublicKey(feeWalletStr);

  const discriminator = await getIxDiscriminator("subscribe_sol"); // Rust fn name

  const keys = [
    { pubkey: user, isSigner: true, isWritable: true },
    { pubkey: configPda, isSigner: false, isWritable: false },
    { pubkey: feeWallet, isSigner: false, isWritable: true },
    { pubkey: subscriptionPda, isSigner: false, isWritable: true },
    { pubkey: SystemProgram.programId, isSigner: false, isWritable: false }
  ];

  return new TransactionInstruction({
    programId: PROGRAM_ID,
    keys,
    data: discriminator // no args
  });
}

export async function sendSubscribeSolTx(
  connection: Connection,
  wallet: WalletContextState
): Promise<string> {
  if (!wallet.publicKey || !wallet.signTransaction) {
    throw new Error("Wallet not connected");
  }

  const ix = await buildSubscribeSolIx(wallet.publicKey);
  const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash("finalized");

  const tx = new Transaction().add(ix);
  tx.feePayer = wallet.publicKey;
  tx.recentBlockhash = blockhash;

  const signed = await wallet.signTransaction(tx);
  const sig = await connection.sendRawTransaction(signed.serialize(), {
    skipPreflight: false
  });

  await connection.confirmTransaction(
    { signature: sig, blockhash, lastValidBlockHeight },
    "confirmed"
  );

  return sig;
}

export async function pollSubscriptionPda(
  connection: Connection,
  user: PublicKey,
  timeoutMs = 60_000,
  intervalMs = 3_000
): Promise<boolean> {
  const pda = getSubscriptionPda(user);
  const start = Date.now();

  while (Date.now() - start < timeoutMs) {
    const info = await connection.getAccountInfo(pda, { commitment: "confirmed" });
    if (info && info.data && info.data.length >= 48) {
      const data = info.data as Buffer | Uint8Array;
      // expires_at at offset 40 (i64 LE)
      const view = new DataView(
        (data as Uint8Array).buffer,
        (data as Uint8Array).byteOffset + 40,
        8
      );
      const expiresAt = Number(view.getBigInt64(0, true));
      const now = Math.floor(Date.now() / 1000);
      if (expiresAt > now) {
        return true;
      }
    }
    await new Promise((res) => setTimeout(res, intervalMs));
  }

  return false;
}

