import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
  /** Custom fallback UI. If not provided, a default error screen is shown. */
  fallback?: ReactNode;
  /** Callback to retry the failed operation (for partial error recovery). */
  onRetry?: () => void;
  /** Module name for user-facing error messages. */
  moduleName?: string;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error:", error, errorInfo);
  }

  private handleRetry = () => {
    this.setState({ hasError: false, error: undefined });
    this.props.onRetry?.();
  };

  public render() {
    if (this.state.hasError) {
      // Custom fallback takes priority
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Module-level partial error (has moduleName)
      if (this.props.moduleName) {
        return (
          <div className="error-fallback-partial">
            <div className="error-fallback-icon">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="10" cy="10" r="8.5" />
                <line x1="7" y1="7" x2="13" y2="13" />
                <line x1="13" y1="7" x2="7" y2="13" />
              </svg>
            </div>
            <p className="error-fallback-title">데이터를 불러올 수 없습니다</p>
            <p className="error-fallback-module">{this.props.moduleName}</p>
            <button className="error-retry-button" onClick={this.handleRetry}>
              재시도
            </button>
          </div>
        );
      }

      // Global fallback (full-screen)
      return (
        <div className="error-fallback-global">
          <div className="error-fallback-content">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="var(--color-error)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="24" cy="24" r="20" />
              <line x1="24" y1="14" x2="24" y2="28" />
              <line x1="24" y1="32" x2="24" y2="34" />
            </svg>
            <h2 className="error-fallback-heading">서비스에 일시적인 문제가 발생했습니다</h2>
            <p className="error-fallback-desc">
              서버 점검 또는 네트워크 오류가 발생했을 수 있습니다.
              <br />잠시 후 다시 시도해 주세요.
            </p>
            <button className="error-retry-button-primary" onClick={() => window.location.reload()}>
              페이지 새로고침
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
