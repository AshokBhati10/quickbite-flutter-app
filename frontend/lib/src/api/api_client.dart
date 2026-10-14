// Centralized API client. Base URL comes from
// --dart-define=API_BASE_URL=... (public configuration, not a secret).
import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'token_store.dart';

const apiBaseUrl = String.fromEnvironment('API_BASE_URL',
    defaultValue: 'http://localhost:8000');

class ApiException implements Exception {
  final int status;
  final String code;
  final String message;

  const ApiException(
      {required this.status, required this.code, required this.message});

  bool get isAuthExpired => status == 401;
}

class ApiClient {
  final String baseUrl;
  final TokenStore tokens;
  final http.Client _http;

  ApiClient({String? baseUrl, TokenStore? tokens, http.Client? httpClient})
      : baseUrl = baseUrl ?? apiBaseUrl,
        tokens = tokens ?? TokenStore(),
        _http = httpClient ?? http.Client();

  Future<Map<String, dynamic>> _decode(http.Response resp) async {
    dynamic body;
    try {
      body = resp.body.isEmpty ? {} : jsonDecode(resp.body);
    } catch (_) {
      body = {};
    }
    if (resp.statusCode >= 400) {
      final map = body is Map<String, dynamic> ? body : <String, dynamic>{};
      throw ApiException(
        status: resp.statusCode,
        code: (map['code'] ?? 'http_error').toString(),
        message: (map['message'] ?? map['detail'] ?? 'Request failed.').toString(),
      );
    }
    return body is Map<String, dynamic> ? body : <String, dynamic>{};
  }

  Future<Map<String, String>> _headers(
      {String? idempotencyKey, bool auth = true}) async {
    final headers = <String, String>{
      'Content-Type': 'application/json',
      // Bypasses the ngrok free-tier browser interstitial on API calls; a
      // no-op for any other host.
      'ngrok-skip-browser-warning': 'true',
    };
    if (auth) {
      final token = await tokens.read();
      if (token != null) headers['Authorization'] = 'Bearer $token';
    }
    if (idempotencyKey != null) headers['Idempotency-Key'] = idempotencyKey;
    return headers;
  }

  Future<Map<String, dynamic>> login(String email, String password) async {
    final resp = await _http
        .post(Uri.parse('$baseUrl/api/v1/auth/login'),
            headers: await _headers(auth: false),
            body: jsonEncode({'email': email, 'password': password}))
        .timeout(const Duration(seconds: 15));
    final body = await _decode(resp);
    await tokens.write((body['access_token'] as String));
    return body;
  }

  Future<Map<String, dynamic>> register(
      String email, String password, String name) async {
    final resp = await _http
        .post(Uri.parse('$baseUrl/api/v1/auth/register'),
            headers: await _headers(auth: false),
            body: jsonEncode({'email': email, 'password': password, 'name': name}))
        .timeout(const Duration(seconds: 15));
    final body = await _decode(resp);
    await tokens.write((body['access_token'] as String));
    return body;
  }

  Future<void> signOut() => tokens.clear();

  Future<Map<String, dynamic>> getJson(String path,
      {Map<String, String>? query}) async {
    final uri =
        Uri.parse('$baseUrl$path').replace(queryParameters: query);
    try {
      final resp = await _http
          .get(uri, headers: await _headers())
          .timeout(const Duration(seconds: 15));
      return await _decode(resp);
    } on TimeoutException {
      throw const ApiException(
          status: 0, code: 'timeout', message: 'Request timed out.');
    } on ApiException {
      rethrow;
    } catch (_) {
      throw const ApiException(
          status: 0, code: 'network_error', message: 'Network error.');
    }
  }

  /// Checkout with an explicit idempotency key. A timeout leaves the outcome
  /// unknown: callers must retry with the SAME key, never mint a new order.
  Future<CheckoutResult> checkout(
      {required Map<String, dynamic> body, required String idempotencyKey}) async {
    try {
      final resp = await _http
          .post(Uri.parse('$baseUrl/api/v1/orders'),
              headers: await _headers(idempotencyKey: idempotencyKey),
              body: jsonEncode(body))
          .timeout(const Duration(seconds: 15));
      final decoded = await _decode(resp);
      return CheckoutResult(
          orderId: (decoded['order_id'] ?? '') as String,
          status: (decoded['status'] ?? '') as String,
          totalMinor: (decoded['total_amount_minor'] ?? 0) as int,
          currency: (decoded['currency'] ?? 'INR') as String,
          timedOut: false);
    } on TimeoutException {
      return const CheckoutResult(
          orderId: '', status: '', totalMinor: 0, currency: 'INR', timedOut: true);
    } on ApiException {
      rethrow;
    } catch (_) {
      throw const ApiException(
          status: 0, code: 'network_error', message: 'Network error.');
    }
  }
}

class CheckoutResult {
  final String orderId;
  final String status;
  final int totalMinor;
  final String currency;
  final bool timedOut;

  const CheckoutResult(
      {required this.orderId,
      required this.status,
      required this.totalMinor,
      required this.currency,
      required this.timedOut});
}
