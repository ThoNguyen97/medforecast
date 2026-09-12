import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';

/**
 * Chặn lỗi render của MỘT trang, không để nó làm trắng cả ứng dụng.
 *
 * Vì sao cần: React gỡ toàn bộ cây khi có lỗi ném ra trong lúc render mà không
 * component nào bắt. Trước đây ứng dụng không có ranh giới nào, nên một lỗi
 * nhỏ ở một trang (ví dụ tham chiếu tới biến khai sai scope) làm mất luôn cả
 * thanh điều hướng — người dùng chỉ thấy màn hình trắng, không có manh mối nào.
 *
 * Đặt bên trong Layout để khi một trang hỏng thì sidebar và header vẫn còn,
 * người dùng chuyển sang trang khác được.
 */
interface Props {
  children: ReactNode;
  /** Đổi giá trị này (ví dụ theo đường dẫn) sẽ tự reset ranh giới lỗi. */
  resetKey?: string;
}

interface State {
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Giữ nguyên trên console để còn xem stack trace khi phát triển.
    console.error('[ErrorBoundary] Trang bị lỗi khi render:', error, info);
  }

  componentDidUpdate(prev: Props) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="max-w-2xl mx-auto mt-10 bg-white rounded-2xl border border-red-200 p-6">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-red-50 flex items-center justify-center shrink-0">
            <AlertTriangle className="w-5 h-5 text-red-600" />
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-lg font-semibold text-neutral-900">
              Trang này gặp lỗi và không hiển thị được
            </h2>
            <p className="text-sm text-neutral-600 mt-1">
              Các trang khác vẫn dùng bình thường — chọn một mục khác ở thanh bên.
              Nếu lỗi lặp lại, gửi nội dung bên dưới cho người phát triển.
            </p>
            <pre className="mt-3 text-xs bg-neutral-50 border border-neutral-200 rounded-lg p-3 overflow-x-auto text-red-700 whitespace-pre-wrap">
              {error.message}
            </pre>
            <button
              type="button"
              onClick={() => this.setState({ error: null })}
              className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
            >
              <RotateCcw className="w-4 h-4" />
              Thử hiển thị lại
            </button>
          </div>
        </div>
      </div>
    );
  }
}
