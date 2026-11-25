import { Component, type ReactNode, type ErrorInfo } from "react";
import { Button } from "./ui/button";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center p-12 text-center">
          <div className="w-12 h-12 bg-muted rounded-full flex items-center justify-center mb-4">
            <span className="text-muted-foreground text-xl">!</span>
          </div>
          <p className="text-sm text-foreground mb-1">Произошла ошибка</p>
          <p className="text-xs text-muted-foreground mb-4">Попробуйте повторить действие или обновить страницу</p>
          <div className="flex items-center gap-3">
            <Button onClick={() => this.setState({ hasError: false })}>
              Попробовать снова
            </Button>
            <Button variant="outline" onClick={() => window.location.reload()}>
              Обновить страницу
            </Button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
