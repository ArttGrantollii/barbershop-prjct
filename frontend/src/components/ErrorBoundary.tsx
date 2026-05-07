import { Component, type ErrorInfo, type ReactNode } from "react"

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

/**
 * Catches render-time errors anywhere below it in the tree and shows a
 * fallback instead of the React-default white screen. Lives at the App
 * root so a single broken page can't take down the whole shell.
 *
 * React 18 still requires this to be a class component — there is no
 * `useErrorBoundary` hook in the stable API.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Surface to the dev console with the React component stack so the
    // failure is debuggable. In production this is where you'd hand off
    // to an error-reporting service (Sentry, Rollbar, etc.).
    console.error("[ErrorBoundary]", error, info.componentStack)
  }

  private reset = (): void => {
    this.setState({ error: null })
  }

  render(): ReactNode {
    if (!this.state.error) return this.props.children

    return (
      <div className="min-h-screen flex items-center justify-center px-6">
        <div className="max-w-md w-full border border-border p-10 flex flex-col gap-6">
          <div>
            <p className="text-[10px] tracking-[0.5em] uppercase text-muted-foreground mb-3">
              Something went wrong
            </p>
            <h1 className="font-display text-4xl uppercase leading-none">
              Page error
            </h1>
          </div>
          <p className="text-xs text-muted-foreground tracking-wider leading-relaxed">
            The page hit an unexpected error and couldn't render. The rest of
            the app is still working — try going home or reloading.
          </p>
          {import.meta.env.DEV && (
            <pre className="text-[11px] leading-relaxed text-destructive/80 whitespace-pre-wrap break-words border-t border-border pt-4">
              {this.state.error.message}
            </pre>
          )}
          <div className="flex gap-3">
            <button
              onClick={this.reset}
              className="flex-1 px-5 py-3 text-xs tracking-widest uppercase border border-border hover:bg-secondary transition-colors"
            >
              Try again
            </button>
            <a
              href="/"
              className="flex-1 px-5 py-3 text-xs tracking-widest uppercase bg-foreground text-background hover:bg-foreground/90 transition-colors text-center"
            >
              Go home
            </a>
          </div>
        </div>
      </div>
    )
  }
}
