# Hướng dẫn ép buộc Google Chrome trên macOS sử dụng AdGuard DNS Family và Google SafeSearch

Tài liệu này tổng hợp các bước kỹ thuật để xử lý triệt để tình trạng trình duyệt Google Chrome trên macOS bỏ qua (bypass) cấu hình AdGuard DNS Family, dẫn đến việc không chặn được các trang web người lớn (18+) và kết quả tìm kiếm nhạy cảm trên Google Search.

## Vấn đề cốt lõi

- Khác với Safari trên iOS/macOS (tuân thủ tuyệt đối cấu hình DNS hệ thống), Google Chrome sử dụng nhân Blink/Chromium có bộ giải mã DNS độc lập (Async DNS) và giao thức mạng riêng (QUIC / HTTP3).
- Khi cài đặt Profile AdGuard DNS ở cấp độ hệ thống macOS (`.mobileconfig`), Chrome thường xuyên bypass cấu hình này để phân giải tên miền trực tiếp, làm vô hiệu hóa khả năng chặn web 18+ và tính năng SafeSearch.
- Việc sử dụng dòng lệnh Terminal (`defaults write`) để ghi chính sách (policy) trên các phiên bản macOS mới thường chỉ được Chrome ghi nhận ở mức **`Recommended`** (Khuyến nghị) áp dụng cho **`Current user`**, cho phép tài khoản Google hoặc cài đặt trình duyệt dễ dàng qua mặt, đặc biệt khi sử dụng Guest Mode.

## Giải pháp: Sử dụng Configuration Profile (Cấp System / Mandatory)

Để ép Chrome tuân thủ 100% cấu hình (chuyển sang trạng thái **`Mandatory`** áp dụng cho toàn bộ **`Machine`**), phương pháp chuẩn xác nhất do Apple và Google hỗ trợ là tạo và cài đặt một file **Apple Configuration Profile (`.mobileconfig`)** riêng cho cấu hình Chrome.

### Các thiết lập Policy được áp dụng:

- **`DnsOverHttpsMode`** (`secure`): Bắt buộc Chrome sử dụng DNS over HTTPS.
- **`DnsOverHttpsTemplates`** (`https://family.adguard-dns.com/dns-query`): Chỉ định chính xác URL DoH của AdGuard DNS Family.
- **`ForceGoogleSafeSearch`** (`true`): Cưỡng chế Google Search lọc sạch kết quả 18+ ngay từ khâu tìm kiếm (không phụ thuộc vào phân giải DNS).
- **`BrowserGuestModeEnabled`** (`false`): Vô hiệu hóa chế độ Guest (Khách) để tránh lách luật bằng môi trường trình duyệt trắng.

---

## Các bước triển khai

### Bước 1: Dọn dẹp cấu hình cũ

Xóa các cấu hình bị kẹt ở mức User (Recommended) gây xung đột.
Mở Terminal và chạy lệnh:

```bash
defaults delete com.google.Chrome
```

### Bước 2: Tạo file `.mobileconfig` cho Chrome Policy

Sinh ra file cấu hình trên Desktop bằng cách copy và dán toàn bộ khối lệnh sau vào Terminal, rồi nhấn Enter:

```bash
cat << 'EOF' > ~/Desktop/ChromeSafeSearch.mobileconfig
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadContent</key>
    <array>
        <dict>
            <key>ForceGoogleSafeSearch</key>
            <true/>
            <key>BrowserGuestModeEnabled</key>
            <false/>
            <key>DnsOverHttpsMode</key>
            <string>secure</string>
            <key>DnsOverHttpsTemplates</key>
            <string>https://family.adguard-dns.com/dns-query</string>
            <key>PayloadDisplayName</key>
            <string>Google Chrome Policies</string>
            <key>PayloadIdentifier</key>
            <string>com.google.Chrome.policy</string>
            <key>PayloadType</key>
            <string>com.google.Chrome</string>
            <key>PayloadUUID</key>
            <string>819E7586-72F0-4C9D-9457-302E1CEB2C79</string>
            <key>PayloadVersion</key>
            <integer>1</integer>
        </dict>
    </array>
    <key>PayloadDisplayName</key>
    <string>Ép Chrome dùng SafeSearch và AdGuard</string>
    <key>PayloadIdentifier</key>
    <string>com.google.Chrome.policy.profile</string>
    <key>PayloadScope</key>
    <string>System</string>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>890A9292-CDE1-4D0E-B8F5-8ADEEBF7C186</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
</dict>
</plist>
EOF
```

### Bước 3: Cài đặt Profile vào macOS

1. Trở ra màn hình Desktop, nhấp đúp vào file **`ChromeSafeSearch.mobileconfig`**.
2. Mở **System Settings** (Cài đặt hệ thống) -> **Privacy & Security** (Quyền riêng tư & Bảo mật) -> cuộn xuống tìm và chọn **Profiles** (Hồ sơ).
3. Bấm đúp vào Profile có tên **"Ép Chrome dùng SafeSearch và AdGuard"** vừa xuất hiện.
4. Chọn **Install** (Cài đặt) và nhập mật khẩu quản trị máy Mac để xác nhận.

### Bước 4: Khởi động lại và Kiểm tra

1. Nhấn `Command + Q` để tắt hoàn toàn tiến trình Chrome và mở lại trình duyệt.
2. Truy cập URL: **`chrome://policy`**
3. Bấm nút **Reload policies**.
4. **Tiêu chuẩn thành công:**
   - Cột **Applies to** chuyển thành **`Machine`**.
   - Cột **Level** chuyển thành **`Mandatory`**.
   - Cả 4 chính sách (ForceGoogleSafeSearch, BrowserGuestModeEnabled, DnsOverHttpsMode, DnsOverHttpsTemplates) đều hiển thị và có trạng thái `OK`.
