import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Keep the console useful in development; no conversation content is logged.
    console.error("Unhandled UI error", error.name, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.error === null) {
      return this.props.children;
    }

    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 bg-surface-bg px-6 text-center">
        <h1 className="text-[20px] font-semibold">Something went wrong</h1>
        <p className="max-w-md text-[13px] leading-relaxed text-text-secondary">
          The interface hit an unexpected error. Your conversations are stored on the server and are
          not affected.
        </p>
        <button
          type="button"
          onClick={() => this.setState({ error: null })}
          className="rounded-lg border border-surface-border-subtle bg-surface-elevated px-3.5 py-2 text-[13px] font-medium transition-colors hover:bg-surface-hover"
        >
          Try again
        </button>
      </div>
    );
  }
}
