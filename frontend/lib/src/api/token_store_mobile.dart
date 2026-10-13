// Mobile adapter: persistent token in platform secure storage.
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

const _key = 'quickbite_access_token';
const _storage = FlutterSecureStorage();

Future<String?> readToken() async => _storage.read(key: _key);
Future<void> writeToken(String token) async =>
    _storage.write(key: _key, value: token);
Future<void> clearToken() async => _storage.delete(key: _key);
