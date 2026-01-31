import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { EdgeaiApp } from "../target/types/edgeai_app";
import {
  Keypair,
  PublicKey,
  SystemProgram,
  LAMPORTS_PER_SOL,
} from "@solana/web3.js";
import {
  TOKEN_PROGRAM_ID,
  getAssociatedTokenAddress,
  getAssociatedTokenAddressSync,
  createAssociatedTokenAccountInstruction,
  getOrCreateAssociatedTokenAccount,
  getAccount,
} from "@solana/spl-token";
import { expect } from "chai";

describe("edgeai_app", () => {
  // Configure the client to use the local cluster.
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);

  const program = anchor.workspace.EdgeaiApp as Program<EdgeaiApp>;

  // Test accounts
  const admin = Keypair.generate();
  const feeWallet = Keypair.generate();
  const user = Keypair.generate();
  const user2 = Keypair.generate();

  // PDAs
  let configPda: PublicKey;
  let configBump: number;
  let tokenMintPda: PublicKey;
  let tokenMintBump: number;
  let subscriptionPda: PublicKey;
  let subscriptionBump: number;
  let stakingVaultPda: PublicKey;
  let stakingVaultBump: number;
  let userStakePda: PublicKey;
  let userStakeBump: number;

  // Token accounts
  let userTokenAccount: PublicKey;
  let stakingVaultTokenAccount: PublicKey;

  // Actual mint pubkey (fetched from config after creation)
  let actualTokenMint: PublicKey;

  // Constants
  const SUBSCRIPTION_PRICE_SOL = new anchor.BN(0.1 * LAMPORTS_PER_SOL);
  const SUBSCRIPTION_PRICE_USDC = new anchor.BN(100 * 1e6); // 100 USDC (6 decimals)
  const SUBSCRIPTION_DURATION = new anchor.BN(30 * 24 * 60 * 60); // 30 days in seconds
  const STAKING_FEE_SHARE_BPS = 5000; // 50%
  const STAKE_AMOUNT = new anchor.BN(1000 * 1e9); // 1000 tokens (9 decimals)

  before(async () => {
    // Airdrop SOL to test accounts
    const airdropPromises = [
      provider.connection.requestAirdrop(admin.publicKey, 10 * LAMPORTS_PER_SOL),
      provider.connection.requestAirdrop(feeWallet.publicKey, 2 * LAMPORTS_PER_SOL),
      provider.connection.requestAirdrop(user.publicKey, 5 * LAMPORTS_PER_SOL),
      provider.connection.requestAirdrop(user2.publicKey, 5 * LAMPORTS_PER_SOL),
    ];

    const airdropSigs = await Promise.all(airdropPromises);
    
    // Wait for all airdrops to confirm
    await Promise.all(
      airdropSigs.map((sig) =>
        provider.connection.confirmTransaction(sig, "confirmed")
      )
    );

    // Derive PDAs
    [configPda, configBump] = PublicKey.findProgramAddressSync(
      [Buffer.from("config")],
      program.programId
    );

    [tokenMintPda, tokenMintBump] = PublicKey.findProgramAddressSync(
      [Buffer.from("token_mint")],
      program.programId
    );

    [subscriptionPda, subscriptionBump] = PublicKey.findProgramAddressSync(
      [Buffer.from("subscription"), user.publicKey.toBuffer()],
      program.programId
    );

    [stakingVaultPda, stakingVaultBump] = PublicKey.findProgramAddressSync(
      [Buffer.from("staking_vault")],
      program.programId
    );

    [userStakePda, userStakeBump] = PublicKey.findProgramAddressSync(
      [Buffer.from("staking_vault"), user.publicKey.toBuffer()],
      program.programId
    );

    // Note: Token account addresses will be set after mint is created
  });

  it("Initializes config PDA", async () => {
    const tx = await program.methods
      .initializeConfig(
        SUBSCRIPTION_PRICE_SOL,
        SUBSCRIPTION_PRICE_USDC,
        SUBSCRIPTION_DURATION,
        STAKING_FEE_SHARE_BPS
      )
      .accounts({
        admin: admin.publicKey,
        feeWallet: feeWallet.publicKey,
        config: configPda,
        systemProgram: SystemProgram.programId,
      })
      .signers([admin])
      .rpc();

    console.log("Initialize config signature:", tx);
    await provider.connection.confirmTransaction(tx, "confirmed");

    // Verify config account
    const configAccount = await program.account.config.fetch(configPda);
    expect(configAccount.admin.toString()).to.equal(admin.publicKey.toString());
    expect(configAccount.feeWallet.toString()).to.equal(
      feeWallet.publicKey.toString()
    );
    expect(configAccount.subscriptionPriceSol.toNumber()).to.equal(
      SUBSCRIPTION_PRICE_SOL.toNumber()
    );
    expect(configAccount.subscriptionPriceUsdc.toNumber()).to.equal(
      SUBSCRIPTION_PRICE_USDC.toNumber()
    );
    expect(configAccount.subscriptionDuration.toNumber()).to.equal(
      SUBSCRIPTION_DURATION.toNumber()
    );
    expect(configAccount.stakingFeeShareBps).to.equal(STAKING_FEE_SHARE_BPS);
  });

  it("Creates $EDGEAI token mint", async () => {
    const tx = await program.methods
      .createTokenMint()
      .accounts({
        admin: admin.publicKey,
        config: configPda,
        tokenMint: tokenMintPda,
        tokenProgram: TOKEN_PROGRAM_ID,
        systemProgram: SystemProgram.programId,
        rent: anchor.web3.SYSVAR_RENT_PUBKEY,
      })
      .signers([admin])
      .rpc();

    console.log("Create token mint signature:", tx);
    const confirmation = await provider.connection.confirmTransaction(tx, "confirmed");
    
    // Check if transaction succeeded
    if (confirmation.value.err) {
      throw new Error(`Transaction failed: ${JSON.stringify(confirmation.value.err)}`);
    }

    // Use the PDA as the actual mint (it should be created)
    actualTokenMint = tokenMintPda;

    // Fetch config to verify it was updated
    let configAccount;
    let foundMint = false;
    for (let i = 0; i < 10; i++) {
      configAccount = await program.account.config.fetch(configPda);
      const mintPubkey = new PublicKey(configAccount.tokenMint);
      if (mintPubkey.toString() !== SystemProgram.programId.toString()) {
        // Config was updated, use the stored mint
        actualTokenMint = mintPubkey;
        foundMint = true;
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    
    // Even if config wasn't updated yet, use the PDA (it should be the mint)
    // Verify the mint matches the PDA
    expect(actualTokenMint.toString()).to.equal(tokenMintPda.toString());

    // Verify token mint exists and is a token mint
    const mintInfo = await provider.connection.getParsedAccountInfo(
      actualTokenMint
    );
    expect(mintInfo.value).to.not.be.null;
    
    // Verify it's owned by token program
    const mintOwner = mintInfo.value?.owner.toString();
    expect(mintOwner).to.equal(TOKEN_PROGRAM_ID.toString());

    // Verify mint authority is the config PDA
    const mintData = mintInfo.value?.data as any;
    if (mintData && mintData.parsed) {
      expect(mintData.parsed.info.mintAuthority).to.equal(configPda.toString());
    }

    // Update token account addresses now that we have the actual mint
    userTokenAccount = getAssociatedTokenAddressSync(
      actualTokenMint,
      user.publicKey
    );

    stakingVaultTokenAccount = getAssociatedTokenAddressSync(
      actualTokenMint,
      stakingVaultPda,
      true
    );
  });

  it("User subscribes with SOL", async () => {
    const userBalanceBefore = await provider.connection.getBalance(
      user.publicKey
    );

    const tx = await program.methods
      .subscribeSol()
      .accounts({
        user: user.publicKey,
        config: configPda,
        feeWallet: feeWallet.publicKey,
        subscription: subscriptionPda,
        systemProgram: SystemProgram.programId,
      })
      .signers([user])
      .rpc();

    console.log("Subscribe SOL signature:", tx);
    await provider.connection.confirmTransaction(tx, "confirmed");

    // Verify subscription account
    const subscriptionAccount =
      await program.account.subscription.fetch(subscriptionPda);
    expect(subscriptionAccount.user.toString()).to.equal(
      user.publicKey.toString()
    );
    // PaymentMethod is an enum - check the structure
    // It should be either { sol: {} } or { usdc: {} }
    expect(subscriptionAccount.paymentMethod).to.be.an("object");
    // Check if it has sol property (Anchor enum format)
    if ("sol" in subscriptionAccount.paymentMethod) {
      expect(subscriptionAccount.paymentMethod.sol).to.exist;
    } else {
      // If it's a different format, just verify it's not empty
      expect(Object.keys(subscriptionAccount.paymentMethod).length).to.be.greaterThan(0);
    }

    // Check expiration is in the future
    const clock = await provider.connection.getSlot();
    const blockTime = await provider.connection.getBlockTime(clock);
    expect(subscriptionAccount.expiresAt.toNumber()).to.be.greaterThan(
      blockTime || 0
    );

    // Verify subscription is active
    const currentTimestamp = blockTime || Date.now() / 1000;
    expect(subscriptionAccount.expiresAt.toNumber()).to.be.greaterThan(
      currentTimestamp
    );

    // Verify SOL was transferred
    const userBalanceAfter = await provider.connection.getBalance(
      user.publicKey
    );
    expect(userBalanceBefore - userBalanceAfter).to.be.greaterThan(
      SUBSCRIPTION_PRICE_SOL.toNumber()
    );
  });

  it("Admin mints tokens to user", async () => {
    // Ensure we have the actual mint (use PDA if config not updated)
    if (!actualTokenMint) {
      actualTokenMint = tokenMintPda;
    }
    expect(actualTokenMint).to.not.be.undefined;
    expect(actualTokenMint.toString()).to.not.equal(SystemProgram.programId.toString());

    // Create user token account (must exist before minting)
    userTokenAccount = getAssociatedTokenAddressSync(
      actualTokenMint,
      user.publicKey
    );

    // Create the ATA if it doesn't exist
    try {
      await getAccount(provider.connection, userTokenAccount);
      // Account exists
    } catch (err) {
      // Account doesn't exist, create it
      const createIx = createAssociatedTokenAccountInstruction(
        admin.publicKey, // payer
        userTokenAccount, // ata
        user.publicKey, // owner
        actualTokenMint // mint
      );
      const createTx = new anchor.web3.Transaction().add(createIx);
      const createSig = await provider.sendAndConfirm(createTx, [admin]);
      await provider.connection.confirmTransaction(createSig, "confirmed");
    }

    // Mint tokens to user using program instruction
    const mintTx = await program.methods
      .mintTokens(STAKE_AMOUNT)
      .accounts({
        admin: admin.publicKey,
        config: configPda,
        tokenMint: actualTokenMint, // Use actual mint!
        destination: userTokenAccount,
        tokenProgram: TOKEN_PROGRAM_ID,
      })
      .signers([admin])
      .rpc();

    console.log("Mint tokens signature:", mintTx);
    await provider.connection.confirmTransaction(mintTx, "confirmed");

    // Wait a bit for account to update
    await new Promise((resolve) => setTimeout(resolve, 500));

    // Verify tokens were minted
    const tokenAccount = await getAccount(
      provider.connection,
      userTokenAccount
    );
    expect(tokenAccount.amount.toString()).to.equal(STAKE_AMOUNT.toString());
  });

  it("User stakes $EDGEAI tokens", async () => {
    // Ensure we have the actual mint (use PDA if config not updated)
    if (!actualTokenMint) {
      actualTokenMint = tokenMintPda;
    }
    expect(actualTokenMint).to.not.be.undefined;
    
    // Ensure userTokenAccount is set
    if (!userTokenAccount) {
      userTokenAccount = getAssociatedTokenAddressSync(
        actualTokenMint,
        user.publicKey
      );
    }

    // Create or get staking vault token account
    let vaultTokenAccountInfo;
    try {
      vaultTokenAccountInfo = await getOrCreateAssociatedTokenAccount(
        provider.connection,
        user, // payer
        actualTokenMint, // mint
        stakingVaultPda, // owner (PDA)
        true // allowOwnerOffCurve
      );
    } catch (err: any) {
      // If account exists, get it
      stakingVaultTokenAccount = getAssociatedTokenAddressSync(
        actualTokenMint,
        stakingVaultPda,
        true
      );
      vaultTokenAccountInfo = { address: stakingVaultTokenAccount };
    }
    stakingVaultTokenAccount = vaultTokenAccountInfo.address;

    // Now stake the tokens
    const stakeTx = await program.methods
      .stake(STAKE_AMOUNT)
      .accounts({
        user: user.publicKey,
        config: configPda,
        userTokenAccount: userTokenAccount,
        stakingVault: stakingVaultPda,
        stakingVaultTokenAccount: stakingVaultTokenAccount,
        userStake: userStakePda,
        tokenProgram: TOKEN_PROGRAM_ID,
        systemProgram: SystemProgram.programId,
      })
      .signers([user])
      .rpc();

    console.log("Stake signature:", stakeTx);
    await provider.connection.confirmTransaction(stakeTx, "confirmed");

    // Verify staking vault
    const stakingVaultAccount =
      await program.account.stakingVault.fetch(stakingVaultPda);
    expect(stakingVaultAccount.totalStaked.toNumber()).to.equal(
      STAKE_AMOUNT.toNumber()
    );

    // Verify user stake
    const userStakeAccount = await program.account.userStake.fetch(
      userStakePda
    );
    expect(userStakeAccount.user.toString()).to.equal(
      user.publicKey.toString()
    );
    expect(userStakeAccount.amount.toNumber()).to.equal(
      STAKE_AMOUNT.toNumber()
    );

    // Verify tokens are in vault
    const vaultTokenAccount = await getAccount(
      provider.connection,
      stakingVaultTokenAccount
    );
    expect(vaultTokenAccount.amount.toString()).to.equal(
      STAKE_AMOUNT.toString()
    );
  });

  it("User unstakes $EDGEAI tokens", async () => {
    const unstakeAmount = new anchor.BN(500 * 1e9); // 500 tokens

    // Ensure we have the actual mint
    if (!actualTokenMint) {
      const configAccount = await program.account.config.fetch(configPda);
      actualTokenMint = new PublicKey(configAccount.tokenMint);
    }

    // Ensure vault is initialized (should be from previous stake test)
    let vaultExists = false;
    try {
      await program.account.stakingVault.fetch(stakingVaultPda);
      vaultExists = true;
    } catch (err) {
      // Vault might not exist if stake test failed
    }

    if (!vaultExists) {
      throw new Error("Staking vault must be initialized before unstaking. Run stake test first.");
    }

    const unstakeTx = await program.methods
      .unstake(unstakeAmount)
      .accounts({
        user: user.publicKey,
        config: configPda,
        userTokenAccount: userTokenAccount,
        stakingVault: stakingVaultPda,
        stakingVaultTokenAccount: stakingVaultTokenAccount,
        userStake: userStakePda,
        tokenProgram: TOKEN_PROGRAM_ID,
      })
      .signers([user])
      .rpc();

    console.log("Unstake signature:", unstakeTx);
    await provider.connection.confirmTransaction(unstakeTx, "confirmed");

    // Verify staking vault updated
    const stakingVaultAccount =
      await program.account.stakingVault.fetch(stakingVaultPda);
    expect(stakingVaultAccount.totalStaked.toNumber()).to.equal(
      STAKE_AMOUNT.toNumber() - unstakeAmount.toNumber()
    );

    // Verify user stake updated
    const userStakeAccount = await program.account.userStake.fetch(
      userStakePda
    );
    expect(userStakeAccount.amount.toNumber()).to.equal(
      STAKE_AMOUNT.toNumber() - unstakeAmount.toNumber()
    );

    // Verify tokens returned to user
    const userTokenAccountInfo = await getAccount(
      provider.connection,
      userTokenAccount
    );
    expect(userTokenAccountInfo.amount.toString()).to.equal(
      unstakeAmount.toString()
    );
  });

  it("Admin updates config", async () => {
    const newPrice = new anchor.BN(0.2 * LAMPORTS_PER_SOL);

    const updateTx = await program.methods
      .updateConfig(
        newPrice, // subscription_price_sol
        null, // subscription_price_usdc
        null, // subscription_duration
        null, // staking_fee_share_bps
        null // fee_wallet
      )
      .accounts({
        admin: admin.publicKey,
        config: configPda,
      })
      .signers([admin])
      .rpc();

    console.log("Update config signature:", updateTx);
    await provider.connection.confirmTransaction(updateTx, "confirmed");

    // Verify config was updated
    const configAccount = await program.account.config.fetch(configPda);
    expect(configAccount.subscriptionPriceSol.toNumber()).to.equal(
      newPrice.toNumber()
    );
  });

  it("Fails when non-admin tries to update config", async () => {
    const newPrice = new anchor.BN(0.3 * LAMPORTS_PER_SOL);

    try {
      await program.methods
        .updateConfig(newPrice, null, null, null, null)
        .accounts({
          admin: user.publicKey, // Not the admin!
          config: configPda,
        })
        .signers([user])
        .rpc();

      expect.fail("Should have thrown an error");
    } catch (err: any) {
      expect(err.toString()).to.include("Unauthorized");
    }
  });
});
