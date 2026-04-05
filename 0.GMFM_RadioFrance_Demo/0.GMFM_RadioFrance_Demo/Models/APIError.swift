//
//  APIError.swift
//  0.GMFM_RadioFrance_Demo
//
//  Created by Eglantine Fonrose on 05/04/2026.
//


import Foundation
import SwiftUICore

enum APIError: Error, LocalizedError {
    case invalidURL
    case noData
    case httpError(Int)
    case invalidResponse
    case folderNotFound
    case networkError(Error)
    
    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "URL invalide"
        case .noData:
            return "Aucune donnée reçue"
        case .httpError(let code):
            return "Erreur HTTP \(code)"
        case .invalidResponse:
            return "Réponse invalide du serveur"
        case .folderNotFound:
            return "Dossier non trouvé"
        case .networkError(let error):
            return "Erreur réseau: \(error.localizedDescription)"
        }
    }
}

class APIService {
    
    static let shared = APIService()
    
    private let customSession: URLSession?
    
    private init(session: URLSession? = nil) {
        self.customSession = session
    }
    
    // Pour les tests, permet de créer une instance avec une session spécifique
    static func createForTesting(with session: URLSession) -> APIService {
        return APIService(session: session)
    }
    
    private var session: URLSession {
        return customSession ?? URLSession.shared
    }

    
    var isSimulatorMode: Bool {
        get {
            UserDefaults.standard.bool(forKey: "isSimulatorMode")
        }
        set {
            UserDefaults.standard.set(newValue, forKey: "isSimulatorMode")
            NotificationCenter.default.post(name: NSNotification.Name("BaseURLChanged"), object: nil)
        }
    }
    
    var customIPAddress: String {
        get {
            UserDefaults.standard.string(forKey: "customIPAddress") ?? "http://10.155.210.134:8000"
        }
        set {
            UserDefaults.standard.set(newValue, forKey: "customIPAddress")
            NotificationCenter.default.post(name: NSNotification.Name("BaseURLChanged"), object: nil)
        }
    }
    
    var baseURL: String {
        isSimulatorMode ? "http://localhost:8000" : customIPAddress
    }
    
    func getTodayFolderName() async throws -> String {
        let urlString = "\(baseURL)/api/findTodayFolder?userId=testUser"
                print("🌐 API Call: \(urlString)")
                
                guard let url = URL(string: urlString) else {
                    throw APIError.invalidURL
                }
                
                var request = URLRequest(url: url)
                request.httpMethod = "GET"
                request.setValue("application/json", forHTTPHeaderField: "Accept")
                request.timeoutInterval = 30
                
                do {
                    let (data, response) = try await session.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                print("❌ Response is not HTTPURLResponse")
                throw APIError.invalidResponse
            }
            
            print("📡 Status: \(httpResponse.statusCode)")
            
            if let responseString = String(data: data, encoding: .utf8) {
                print("📦 Body: \(responseString)")
            }
            
            guard httpResponse.statusCode == 200 else {
                throw APIError.httpError(httpResponse.statusCode)
            }
            
            guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                print("❌ Failed to parse JSON as [String: Any]")
                throw APIError.invalidResponse
            }
            
            guard let status = json["status"] as? String, status == "success" else {
                print("❌ Status field is not 'success' or is missing")
                throw APIError.invalidResponse
            }
            
            guard let folderName = json["folderName"] as? String else {
                print("❌ 'folderName' field is missing or not a string")
                throw APIError.folderNotFound
            }
            
            print("✅ Folder found: \(folderName)")
            return folderName
        } catch {
            print("❌ Error in getTodayFolderName: \(error)")
            throw error
        }
    }

    func getUserChronicles() async throws -> [Program] {
        let urlString = "\(baseURL)/api/getUserChronicles?userId=testUser"
                print("🌐 API Call: \(urlString)")
                
                guard let url = URL(string: urlString) else {
                    throw APIError.invalidURL
                }
                
                var request = URLRequest(url: url)
                request.httpMethod = "GET"
                request.setValue("application/json", forHTTPHeaderField: "Accept")
                
                do {
                    let (data, response) = try await session.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                print("❌ Response is not HTTPURLResponse")
                throw APIError.invalidResponse
            }
            
            print("📡 Status: \(httpResponse.statusCode)")
            
            guard httpResponse.statusCode == 200 else {
                throw APIError.httpError((response as? HTTPURLResponse)?.statusCode ?? 500)
            }
            
            if let responseString = String(data: data, encoding: .utf8) {
                print("📦 getUserChronicles Result: \(responseString)")
            }
            
            guard let jsonArray = try JSONSerialization.jsonObject(with: data) as? [[String: Any]] else {
                print("❌ Failed to parse JSON as [[String: Any]]")
                throw APIError.invalidResponse
            }
            
            let programs = jsonArray.compactMap { dict -> Program? in
                guard let name = dict["nomDeChronique"] as? String,
                      let start = dict["startTime"] as? Int,
                      let end = dict["endTime"] as? Int else { return nil }
                
                return Program(
                    time: "--h--",
                    title: name,
                    thumbnail: "mic",
                    color: Color(red: 0.88, green: 0, blue: 0.1),
                    startTime: start,
                    duration: end - start
                )
            }
            
            print("✅ Programs found: \(programs.count)")
            return programs
        } catch {
            print("❌ Error in getUserChronicles: \(error)")
            throw error
        }
    }
    
    func removeChronicles() async throws {
        let urlString = "\(baseURL)/api/removeChronicles?userId=testUser"
        print("🌐 API Call: \(urlString)")
        guard let url = URL(string: urlString) else { throw APIError.invalidURL }
        
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        
        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            print("❌ Response is not HTTPURLResponse")
            throw APIError.invalidResponse
        }
        
        print("📡 Status: \(httpResponse.statusCode)")
        if let body = String(data: data, encoding: .utf8) {
            print("📦 Body: \(body)")
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.httpError(httpResponse.statusCode)
        }
    }
    
    func setUserBaseTime(hour: Int, minute: Int) async throws {
        let urlString = "\(baseURL)/api/setUserBaseTime?userId=testUser&baseHour=\(hour)&baseMinute=\(minute)"
        print("🌐 API Call: \(urlString)")
        guard let url = URL(string: urlString) else { throw APIError.invalidURL }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        
        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        print("📡 Status: \(httpResponse.statusCode)")
        if let body = String(data: data, encoding: .utf8) {
            print("📦 Body: \(body)")
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.httpError(httpResponse.statusCode)
        }
        print("✅ Base time set to \(hour)h\(minute)")
    }
    
    func getUserBaseTime() async throws -> (hour: Int, minute: Int) {
        let urlString = "\(baseURL)/api/getUserBaseTime?userId=testUser"
        print("🌐 API Call: \(urlString)")
        guard let url = URL(string: urlString) else { throw APIError.invalidURL }
        
        let (data, response) = try await session.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw APIError.invalidResponse
        }
        
        let hour = json["baseHour"] as? Int ?? 7
        let minute = json["baseMinute"] as? Int ?? 0
        
        return (hour, minute)
    }
    
    func addChronicle(program: Program) async throws {
        let nameEncoded = program.title.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
        let urlString = "\(baseURL)/api/addChronicle?userId=testUser&nomDeChroniques=\(nameEncoded)&chroniqueRealTimecode=\(program.startTime)&duration=\(program.duration)"
        print("🌐 API Call: \(urlString)")
        
        guard let url = URL(string: urlString) else { throw APIError.invalidURL }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        
        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            print("❌ Response is not HTTPURLResponse")
            throw APIError.invalidResponse
        }
        
        print("📡 Status: \(httpResponse.statusCode)")
        if let body = String(data: data, encoding: .utf8) {
            print("📦 Body: \(body)")
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.httpError(httpResponse.statusCode)
        }
    }
    
    func scheduleAllUserChronicles() async throws {
        let urlString = "\(baseURL)/api/scheduleAllUserChronicles?userId=testUser&baseHour=7&baseMinute=0"
        print("🌐 API Call: \(urlString)")
        
        guard let url = URL(string: urlString) else { throw APIError.invalidURL }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        
        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            print("❌ Response is not HTTPURLResponse")
            throw APIError.invalidResponse
        }
        
        print("📡 Status: \(httpResponse.statusCode)")
        if let body = String(data: data, encoding: .utf8) {
            print("📦 Body: \(body)")
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.httpError(httpResponse.statusCode)
        }
    }
    
    func fetchSchedule() async throws -> Date {
        let urlString = "\(baseURL)/api/getSchedule?userId=testUser"
        print("🌐 API Call: \(urlString)")
        
        guard let url = URL(string: urlString) else {
            throw NSError(domain: "", code: -1,
                  userInfo: [NSLocalizedDescriptionKey: "URL invalide"])
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        
        let (data, _) = try await URLSession.shared.data(for: request)
        
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let hour = json["hour"] as? Int,
              let minute = json["minute"] as? Int else {
            throw NSError(domain: "", code: -3,
                  userInfo: [NSLocalizedDescriptionKey: "Format de réponse invalide"])
        }
        
        var calendar = Calendar.current
        calendar.timeZone = TimeZone(identifier: "Europe/Paris")!
        
        let now = Date()
        let dateComponents = calendar.dateComponents([.year, .month, .day], from: now)
        
        var scheduleComponents = DateComponents()
        scheduleComponents.year = dateComponents.year
        scheduleComponents.month = dateComponents.month
        scheduleComponents.day = dateComponents.day
        scheduleComponents.hour = hour
        scheduleComponents.minute = minute
        scheduleComponents.second = 0
        
        guard let scheduleDate = calendar.date(from: scheduleComponents) else {
            throw NSError(domain: "", code: -4,
                  userInfo: [NSLocalizedDescriptionKey: "Impossible de créer la date"])
        }
        
        return scheduleDate
    }
    
    func getStreamURL() async throws -> URL {
        let folderName = try await getTodayFolderName()
        let folderWithUnderscores = folderName.replacingOccurrences(of: " ", with: "_")
        
        guard let encodedFolder = folderWithUnderscores.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) else {
            throw APIError.invalidURL
        }
        let streamURLString = "\(baseURL)/\(encodedFolder)/playlist.m3u8"
        
        print("🎵 API Call (Stream): \(streamURLString)")
        
        guard let streamURL = URL(string: streamURLString) else {
            throw APIError.invalidURL
        }
        
        return streamURL
    }
    
    func sendPlaylist(chronicleNames: [String]) async throws {
        var urlComponents = URLComponents(string: "\(baseURL)/api/createPlaylist")
        urlComponents?.queryItems = chronicleNames.map { URLQueryItem(name: "chronicles", value: $0) }
        
        guard let url = urlComponents?.url else {
            throw APIError.invalidURL
        }
        
        print("🌐 API Call: \(url.absoluteString)")
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        
        let (_, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.httpError(httpResponse.statusCode)
        }
    }

    func fetchPlaylist() async throws -> [String] {
        let urlString = "\(baseURL)/api/getPlaylist"
        print("🌐 API Call: \(urlString)")
        
        guard let url = URL(string: urlString) else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.httpError((response as? HTTPURLResponse)?.statusCode ?? 500)
        }

        guard let chronicleNames = try JSONSerialization.jsonObject(with: data) as? [String] else {
            throw APIError.invalidResponse
        }

        return chronicleNames
    }
}
