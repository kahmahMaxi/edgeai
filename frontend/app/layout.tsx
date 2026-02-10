import "../app/globals.css";
import { ReactNode } from "react";
import { WalletContextProvider } from "../components/WalletContextProvider";

export const metadata = {
  title: "$EDGEAI dApp",
  description: "Subscribe to $EDGEAI premium on Solana devnet"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-950 text-slate-50">
        <WalletContextProvider>
          <div className="max-w-2xl mx-auto px-4 py-8">
            <header className="mb-8 flex items-center justify-between">
              <h1 className="text-xl font-semibold">$EDGEAI dApp</h1>
            </header>
            {children}
          </div>
        </WalletContextProvider>
      </body>
    </html>
  );
}

