import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold tracking-tight">Okeder</h1>
          <p className="mt-2 text-slate-400">Ok, Ordered!</p>
        </div>
        <SignIn redirectUrl="/dashboard" />
      </div>
    </div>
  );
}
