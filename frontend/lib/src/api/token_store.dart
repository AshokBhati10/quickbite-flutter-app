// Token storage behind a conditional import: in-memory on web,
// secure storage on mobile. Web never claims secure-storage guarantees.
import 'token_store_stub.dart'
    if (dart.library.io) 'token_store_mobile.dart'
    if (dart.library.html) 'token_store_web.dart' as impl;

class TokenStore {
  Future<String?> read() => impl.readToken();
  Future<void> write(String token) => impl.writeToken(token);
  Future<void> clear() => impl.clearToken();
}
