# $EDGEAI Frontend dApp

Simple Next.js dApp for subscribing to $EDGEAI premium on Solana devnet.

## Features

- Connect Phantom wallet via Solana Wallet Adapter
- One-click subscription with SOL to your on-chain Anchor program
- Polls the subscription PDA to confirm activation
- Minimal TailwindCSS UI, deploy-ready for Vercel

## Tech Stack

- Next.js 14 (App Router)
- React 18
- TailwindCSS
- @solana/web3.js
- @solana/wallet-adapter-react (+ Phantom)

## Setup

```bash
cd frontend
cp .env.example .env.local
# edit .env.local with your values
npm install
npm run dev
```

### Environment Variables

Create `frontend/.env.local`:

```bash
NEXT_PUBLIC_RPC_URL=https://api.devnet.solana.com
NEXT_PUBLIC_PROGRAM_ID=2ZfXnm4EnjBfqZtvTao8gdoEb6cp1yMvfppUEVY5svxQ
NEXT_PUBLIC_FEE_WALLET=3vqEDEV6PBvpRc6TSC7grWPNAWGhL4q8mhxfeAubZ6RJ

NEXT_PUBLIC_SUBSCRIBE_SOL_ENABLED=true
NEXT_PUBLIC_SUBSCRIBE_SOL_AMOUNT=0.01
NEXT_PUBLIC_SUBSCRIBE_USDC_ENABLED=true
NEXT_PUBLIC_SUBSCRIBE_USDC_AMOUNT=3
```

## Running Locally

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`:

- `/` – Connect wallet
- `/subscribe` – Click “Subscribe with 0.01 SOL”

## Deploying to Vercel

1. Push the `frontend` folder to your repo
2. Create a new Vercel project, point to `frontend`
3. Set environment variables in Vercel dashboard:
   - `NEXT_PUBLIC_RPC_URL`
   - `NEXT_PUBLIC_PROGRAM_ID`
   - `NEXT_PUBLIC_FEE_WALLET`
   - `NEXT_PUBLIC_SUBSCRIBE_SOL_ENABLED`
   - `NEXT_PUBLIC_SUBSCRIBE_SOL_AMOUNT`
   - `NEXT_PUBLIC_SUBSCRIBE_USDC_ENABLED`
   - `NEXT_PUBLIC_SUBSCRIBE_USDC_AMOUNT`
4. Deploy

## Notes

- The dApp builds the `subscribe_sol` instruction by computing the Anchor discriminator
  (`sha256("global:subscribe_sol")[:8]`) and using the correct PDAs:
  - Config PDA: `["config"]`
  - Subscription PDA: `["subscription", user_pubkey]`
- It then signs and sends the transaction with the connected wallet and polls the
  subscription PDA to confirm that `expires_at > now`.

