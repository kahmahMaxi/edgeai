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
  createAssociatedTokenAccountInstruction,
  createMintToInstruction,
  mintTo,
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

  // Constants
  const SUBSCRIPTION_PRICE_SOL = new anchor.BN(0.1 * LAMPORTS_PER_SOL);
  const SUBSCRIPTION_PRICE_USDC = new anchor.BN(100 * 1e6); // 100 USDC (6 decimals)
  const SUBSCRIPTION_DURATION = new anchor.BN(30 * 24 * 60 * 60); // 30 days in seconds
  const STAKING_FEE_SHARE_BPS = 5000; // 50%
  const STAKE_AMOUNT = new anchor.BN(1000 * 1e9); // 1000 tokens (9 decimals)

  before(async () => {
    // Airdrop SOL to test accounts
    await provider.connection.requestAirdrop(
      admin.publicKey,
      10 * LAMPORTS_PER_SOL
    );
    await provider.connection.requestAirdrop(
      feeWallet.publicKey,
      2 * LAMPORTS_PER_SOL
    );
    await provider.connection.requestAirdrop(
      user.publicKey,
      5 * LAMPORTS_PER_SOL
    );
    await provider.connection.requestAirdrop(
      user2.publicKey,
      5 * LAMPORTS_PER_SOL
    );

    // Wait for airdrops to confirm
    await new Promise((resolve) => setTimeout(resolve, 1000));

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

    // Derive token accounts
    userTokenAccount = await getAssociatedTokenAddress(
      tokenMintPda,
      user.publicKey
    );

    stakingVaultTokenAccount = await getAssociatedTokenAddress(
      tokenMintPda,
      stakingVaultPda,
      true
    );
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

    // Verify token mint exists
    const mintInfo = await provider.connection.getParsedAccountInfo(
      tokenMintPda
    );
    expect(mintInfo.value).to.not.be.null;

    // Verify config was updated with token mint
    const configAccount = await program.account.config.fetch(configPda);
    expect(configAccount.tokenMint.toString()).to.equal(
      tokenMintPda.toString()
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

    // Verify subscription account
    const subscriptionAccount =
      await program.account.subscription.fetch(subscriptionPda);
    expect(subscriptionAccount.user.toString()).to.equal(
      user.publicKey.toString()
    );
    expect(subscriptionAccount.paymentMethod.sol).to.be.true;

    // Check expiration is in the future
    const clock = await provider.connection.getSlot();
    const blockTime = await provider.connection.getBlockTime(clock);
    expect(subscriptionAccount.expiresAt.toNumber()).to.be.greaterThan(
      blockTime || 0
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
    // First, create user token account if it doesn't exist
    try {
      await program.provider.sendAndConfirm(
        new anchor.web3.Transaction().add(
          createAssociatedTokenAccountInstruction(
            user.publicKey, // payer
            userTokenAccount, // ata
            user.publicKey, // owner
            tokenMintPda // mint
          )
        ),
        [user]
      );
    } catch (err) {
      // Account might already exist, that's fine
    }

    // Mint tokens to user using program instruction
    const mintTx = await program.methods
      .mintTokens(STAKE_AMOUNT)
      .accounts({
        admin: admin.publicKey,
        config: configPda,
        tokenMint: tokenMintPda,
        destination: userTokenAccount,
        tokenProgram: TOKEN_PROGRAM_ID,
      })
      .signers([admin])
      .rpc();

    console.log("Mint tokens signature:", mintTx);
  });

  it("User stakes $EDGEAI tokens", async () => {

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
  });

  it("User unstakes $EDGEAI tokens", async () => {
    const unstakeAmount = new anchor.BN(500 * 1e9); // 500 tokens

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
    } catch (err) {
      expect(err.toString()).to.include("Unauthorized");
    }
  });
});
