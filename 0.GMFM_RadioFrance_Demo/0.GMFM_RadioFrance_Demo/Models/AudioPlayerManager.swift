//
//  AudioPlayerManager.swift
//  0.GMFM_RadioFrance_Demo
//
//  Created by Eglantine Fonrose on 05/04/2026.
//


import Foundation
import AVKit
import Combine

// MARK: - Audio Player Manager
@MainActor
class AudioPlayerManager: ObservableObject {
    private var player: AVPlayer?
    private var timeObserver: Any?
    private var cancellables = Set<AnyCancellable>()
    private var itemStatusObserver: NSKeyValueObservation?
    private var timeControlStatusObserver: NSKeyValueObservation?
    private var assetDurationTimer: Timer?
    private var m3u8Parser: M3U8Parser?
    
    @Published var isPlaying = false
    @Published var isBuffering = false
    @Published var currentTime: TimeInterval = 0
    @Published var duration: TimeInterval = 0
    @Published var calculatedDuration: TimeInterval = 0
    @Published var isLoading = true
    @Published var isReloading = false
    @Published var errorMessage: String?
    @Published var isReady = false
    @Published var streamAvailable = false
    @Published var hasPlaybackBeenInitiated = false
    @Published var currentURL: URL?
    @Published var isSeeking = false
    @Published var currentFolderName: String? // New property
    
    private var seekableRangesObserver: NSKeyValueObservation?
    private var loadedTimeRangesObserver: NSKeyValueObservation?
    private var playbackBufferEmptyObserver: NSKeyValueObservation?
    private var playbackLikelyToKeepUpObserver: NSKeyValueObservation?
    private var playbackBufferFullObserver: NSKeyValueObservation?
    private var rateObserver: NSKeyValueObservation?
    
    @Published private(set) var chronicleURLs: [URL] = []
    @Published var programs: [Program] = []
    @Published private(set) var currentChronicleIndex: Int = 0
    @Published private(set) var currentChronicleName: String?
    
    // Statistiques de chargement
    @Published var loadedSegmentsCount: Int = 0
    @Published var totalSegmentsExpected: Int = 0
    @Published var loadingProgress: Double = 0.0
    @Published var isLiveStream: Bool = false
    
    // Mode test pour éviter les effets de bord asynchrones
    var isTestMode = false

    private var retryCount = 0
    private let maxRetryCount = 3
    private var isSeekingInitial = false
    private var isRetrying = false
    private var currentRetryIndex: Int?
    private var lastKnownDuration: TimeInterval = 0
    private var durationCheckTimer: Timer?
    private var pendingSeekTime: TimeInterval?
    private var shouldResumeAfterSeek = false
    private var pendingResetToZero = false
    private var isTransitioningPrograms = false
    private var forceResetToZero = false
    
    // Nouveaux flags pour la gestion du buffer optimisée
    private var isWaitingForBuffer = false
    private var pendingSeekWhileBuffering: TimeInterval?
    private var retrySeekCount = 0
    private let maxRetrySeekCount = 5
    private var lastSeekTime: TimeInterval = 0
    private var seekTimer: Timer?
    private var isSeekPending = false
    
    // Cache des segments chargés pour seeks plus rapides
    private var loadedTimeRangesCache: [CMTimeRange] = []
    private var lastLoadedRangeUpdate: TimeInterval = 0
    
    // Nouvelle propriété pour l'autoplay
    private var shouldAutoPlay = true

    init() {
        self.player = AVPlayer()
        self.m3u8Parser = M3U8Parser()
        setupObservers()
        setupAudioSession()
    }
    
    private func setupAudioSession() {
        do {
            try AVAudioSession.sharedInstance().setCategory(.playback, mode: .default)
            try AVAudioSession.sharedInstance().setActive(true)
        } catch {
            print("❌ Erreur configuration audio: \(error)")
        }
    }

    private var setupTask: Task<Void, Error>?

    func setup() async throws {
        // Si un chargement est déjà en cours, on attend qu\\'il se termine au lieu d\\'en lancer un nouveau
        if let existingTask = setupTask {
            return try await existingTask.value
        }
        
        let task = Task {
            self.isLoading = true
            self.isReloading = true
            self.errorMessage = nil
            
            do {
                // Lancer les deux requêtes en parallèle
                async let folderNameTask = APIService.shared.getTodayFolderName()
                async let programsTask = APIService.shared.getUserChronicles()
                
                // 1. Récupérer et afficher les programmes dès qu\\'ils sont disponibles
                let fetchedPrograms = try await programsTask
                
                self.programs = fetchedPrograms
                if !fetchedPrograms.isEmpty {
                    self.currentChronicleName = fetchedPrograms.first?.title
                    self.errorMessage = nil
                } else {
                    self.errorMessage = "Aucune chronique trouvée."
                }
                
                // 2. Attendre le nom du dossier pour construire les URLs
                let folderName: String?
                do {
                    folderName = try await folderNameTask
                } catch is CancellationError {
                    throw CancellationError()
                } catch {
                    print("⚠️ Dossier non trouvé ou erreur : \(error.localizedDescription)")
                    folderName = nil
                }
                
                self.currentFolderName = folderName
                self.isReloading = false
                
                if let folder = folderName, !fetchedPrograms.isEmpty {
                    let urls = fetchedPrograms.compactMap { program -> URL? in
                        let titleWithUnderscores = program.title.replacingOccurrences(of: " ", with: "_")
                        guard let encodedTitle = titleWithUnderscores.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) else {
                            return nil
                        }
                        let urlString = "\(APIService.shared.baseURL)/\(folder)/\(encodedTitle)/\(encodedTitle).m3u8"
                        return URL(string: urlString)
                    }
                    
                    self.chronicleURLs = urls
                    self.streamAvailable = !urls.isEmpty
                    
                    if !urls.isEmpty {
                        self.playChronicle(at: self.currentChronicleIndex)
                    } else {
                        self.isLoading = false
                        self.errorMessage = "Chronique indisponible pour le moment."
                    }
                } else {
                    self.isLoading = false
                    if !fetchedPrograms.isEmpty && folderName == nil {
                        self.errorMessage = "Les fichiers audio ne sont pas encore disponibles. Réessayez de recharger."
                    }
                }
            } catch is CancellationError {
                // On ne fait rien de spécial, c\\'est une annulation normale (ex: pull-to-refresh annulé)
                print("ℹ️ Setup annulé proprement")
                throw CancellationError()
            } catch {
                self.errorMessage = "Erreur lors du chargement : \(error.localizedDescription)"
                self.isLoading = false
                self.isReloading = false
                self.streamAvailable = false
                throw error
            }
        }
        
        self.setupTask = task
        
        do {
            try await task.value
            self.setupTask = nil
        } catch {
            self.setupTask = nil
            throw error
        }
    }

    private func setupObservers() {
        timeObserver = player?.addPeriodicTimeObserver(forInterval: CMTime(seconds: 0.1, preferredTimescale: 600), queue: .main) { [weak self] time in
            guard let self = self else { return }
            
            // Mise à jour plus fréquente pour meilleure fluidité
            if !self.isSeeking {
                let newTime = time.seconds
                if !newTime.isNaN && !newTime.isInfinite && newTime >= 0 {
                    // Lissage du temps pour éviter les à-coups
                    let smoothedTime = self.smoothTime(newTime)
                    self.currentTime = smoothedTime
                }
            }
            
            // Vérifier si la durée est toujours valide
            if self.duration.isNaN || self.duration.isInfinite || self.duration <= 0 {
                if let item = self.player?.currentItem {
                    self.updateDuration(from: item)
                }
            }
            
            // Mettre à jour le progrès de chargement
            self.updateLoadingProgress()
        }
        
        timeControlStatusObserver = player?.observe(\.timeControlStatus, options: [.new, .old]) { [weak self] player, _ in
            DispatchQueue.main.async {
                // Mettre à jour les états en fonction du statut réel du player
                self?.isPlaying = player.timeControlStatus == .playing
                self?.isBuffering = player.timeControlStatus == .waitingToPlayAtSpecifiedRate
                
                // Si on était en train de seeker et que le player repasse en lecture, on met à jour isSeeking
                if player.timeControlStatus == .playing && self?.isSeeking == true {
                    print("▶️ Player a repris la lecture, fin du seeking")
                    self?.isSeeking = false
                }
            }
        }
        
        // Observateur du taux de lecture pour détecter les problèmes
        rateObserver = player?.observe(\.rate, options: [.new, .old]) { [weak self] player, change in
            if player.rate == 0 && self?.isPlaying == true && self?.isSeeking == false {
                // Le player est censé jouer mais le rate est à 0 -> problème de buffer
                print("⚠️ Rate à 0 alors que isPlaying = true, mise en buffering")
                DispatchQueue.main.async {
                    self?.isBuffering = true
                }
            }
        }
    }
    
    // Lissage du temps pour éviter les à-coups
    private func smoothTime(_ newTime: TimeInterval) -> TimeInterval {
        // Éviter les sauts trop brusques (plus de 0.5 secondes)
        let maxJump: TimeInterval = 0.5
        let timeDiff = abs(newTime - currentTime)
        
        if timeDiff > maxJump && !isSeeking {
            // Si le saut est trop grand, on lisse progressivement
            return currentTime + (newTime > currentTime ? maxJump : -maxJump)
        }
        return newTime
    }
    
    private func updateLoadingProgress() {
        guard let currentItem = player?.currentItem else { return }
        
        // Mettre à jour le cache des ranges chargés
        let now = Date().timeIntervalSince1970
        if now - lastLoadedRangeUpdate > 0.5 { // Mise à jour toutes les 0.5 secondes max
            loadedTimeRangesCache = currentItem.loadedTimeRanges.map { $0.timeRangeValue }
            lastLoadedRangeUpdate = now
        }
        
        var totalLoadedDuration: TimeInterval = 0
        
        for timeRange in loadedTimeRangesCache {
            let startSeconds = timeRange.start.seconds
            let durationSeconds = timeRange.duration.seconds
            
            if !startSeconds.isNaN && !durationSeconds.isNaN {
                totalLoadedDuration += durationSeconds
            }
        }
        
        let totalDuration = max(self.duration, self.calculatedDuration, 1.0)
        self.loadingProgress = min(totalLoadedDuration / totalDuration, 1.0)
    }

    func playChronicle(at index: Int) {
        // Change: Guard against programs.count, not chronicleURLs.count
        guard index >= 0 && index < programs.count else { return }

        // Indiquer qu\\'on est en transition
        isTransitioningPrograms = true
        
        // Réinitialiser les états
        isSeekingInitial = false
        isRetrying = false
        currentRetryIndex = nil
        retryCount = 0
        errorMessage = nil
        duration = 0
        calculatedDuration = 0
        lastKnownDuration = 0
        loadedSegmentsCount = 0
        totalSegmentsExpected = 0
        loadingProgress = 0.0
        isSeeking = false
        pendingSeekTime = nil
        shouldResumeAfterSeek = false
        isWaitingForBuffer = false
        pendingSeekWhileBuffering = nil
        retrySeekCount = 0
        loadedTimeRangesCache = []
        
        // IMPORTANT: On remet à 0 immédiatement pour l\\'UI
        self.currentTime = 0
        self.isPlaying = false
        self.isBuffering = false
        
        // Arrêter les timers existants
        durationCheckTimer?.invalidate()
        assetDurationTimer?.invalidate()
        seekTimer?.invalidate()
        
        currentChronicleIndex = index
        currentChronicleName = programs[index].title
        
        // --- ASYNC LOGIC FOR URL CONSTRUCTION AND PLAYBACK ---
        Task {
            self.isLoading = true // Show loading indicator
            self.errorMessage = nil

            var effectiveFolderName = self.currentFolderName
            if effectiveFolderName == nil {
                print("⚠️ folderName est nil lors de la lecture, tentative de re-chargement...")
                do {
                    effectiveFolderName = try await APIService.shared.getTodayFolderName()
                    self.currentFolderName = effectiveFolderName // Update if successful
                } catch {
                    print("❌ Échec de re-chargement du dossier : \(error.localizedDescription)")
                    self.errorMessage = "Fichiers non disponibles. Réessayez de recharger."
                    self.isLoading = false
                    return // Cannot proceed without folderName
                }
            }

            guard let folder = effectiveFolderName else {
                print("❌ Impossible de récupérer le nom du dossier pour la lecture.")
                self.errorMessage = "Fichiers non disponibles."
                self.isLoading = false
                return
            }

            let program = programs[index]
            let titleWithUnderscores = program.title.replacingOccurrences(of: " ", with: "_")
            guard let encodedTitle = titleWithUnderscores.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) else {
                print("❌ Impossible d\\'encoder le titre de la chronique: \(program.title)")
                self.errorMessage = "Erreur de format de titre."
                self.isLoading = false
                return
            }
            let urlString = "\(APIService.shared.baseURL)/\(folder)/\(encodedTitle)/\(encodedTitle).m3u8"
            guard let url = URL(string: urlString) else {
                print("❌ URL invalide construite: \(urlString)")
                self.errorMessage = "URL de chronique invalide."
                self.isLoading = false
                return
            }
            self.currentURL = url
            print("🎵 Audio Playback Call: \(url.absoluteString)")
            
            // Lancer le parsing M3U8
            parseM3U8Manifest(url: url)
            
            let playerItem = AVPlayerItem(url: url)
            
            // Configuration optimisée pour la fluidité
            playerItem.automaticallyPreservesTimeOffsetFromLive = false
            playerItem.canUseNetworkResourcesForLiveStreamingWhilePaused = true
            
            if #available(iOS 15.0, *) {
                // Augmenter le buffer pour plus de fluidité
                playerItem.preferredForwardBufferDuration = 60.0
            }
            
            // Supprimer l\\'ancien observateur
            NotificationCenter.default.removeObserver(self, name: .AVPlayerItemDidPlayToEndTime, object: player?.currentItem)

            player?.replaceCurrentItem(with: playerItem)
            player?.automaticallyWaitsToMinimizeStalling = false // Désactiver pour plus de contrôle
            
            // Ajouter des observateurs
            setupBufferingObservers(for: playerItem)
            
            // Ajouter un nouvel observateur
            NotificationCenter.default.addObserver(self, selector: #selector(itemDidPlayToEndTime), name: .AVPlayerItemDidPlayToEndTime, object: playerItem)

            observePlayerItemStatus(playerItem)
            
            // Démarrer la vérification périodique de la durée
            startDurationCheckTimer()
            
            // Marquer qu\\'on veut un reset à 0 dès que le player sera prêt
            pendingResetToZero = true
            forceResetToZero = true
        }
    }
    
    // MARK: - Internal for Testing
    func forceResetToBeginning() {
        if isTestMode {
            self.currentTime = 0
            return
        }
        guard let player = player, let currentItem = player.currentItem else {
            print("❌ forceResetToBeginning: player ou item nil, nouvelle tentative dans 0.5s")
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [weak self] in
                self?.forceResetToBeginning()
            }
            return
        }
        
        if currentItem.status == .readyToPlay {
            print("✅ Player prêt, exécution du reset forcé à 0")
            
            let cmTime = CMTime(seconds: 0, preferredTimescale: 600)
            
            player.seek(to: cmTime, toleranceBefore: .zero, toleranceAfter: .zero) { [weak self] finished in
                guard let self = self else { return }
                
                if finished {
                    print("✅ Reset forcé à 0 réussi")
                    
                    // Mettre à jour l'UI
                    DispatchQueue.main.async {
                        self.currentTime = 0
                        self.pendingResetToZero = false
                        self.forceResetToZero = false
                        self.isTransitioningPrograms = false
                        
                        // Lancer la lecture si autoplay est activé
                        if self.shouldAutoPlay {
                            print("▶️ Démarrage automatique de la lecture")
                            self.player?.play()
                            self.isPlaying = true
                            self.isBuffering = false
                        }
                        
                        self.hasPlaybackBeenInitiated = true
                    }
                } else {
                    print("❌ Reset forcé interrompu, nouvelle tentative")
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                        self.forceResetToBeginning()
                    }
                }
            }
        } else if currentItem.status == .failed {
            print("❌ PlayerItem en échec, impossible de reset")
            self.errorMessage = "Impossible de charger la chronique"
            self.isLoading = false
        } else {
            print("⏳ Player pas encore prêt (status: \(currentItem.status.rawValue)), nouvelle tentative dans 0.5s")
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [weak self] in
                self?.forceResetToBeginning()
            }
        }
    }
    
    private func setupBufferingObservers(for playerItem: AVPlayerItem) {
        playbackBufferEmptyObserver = playerItem.observe(\.isPlaybackBufferEmpty, options: [.new]) { [weak self] item, _ in
            if item.isPlaybackBufferEmpty {
                print("⚠️ Buffer vide")
                DispatchQueue.main.async {
                    self?.isWaitingForBuffer = true
                    // Si on était en train de jouer, on met à jour l'état
                    if self?.isPlaying == true {
                        self?.isBuffering = true
                    }
                }
            }
        }
        
        playbackLikelyToKeepUpObserver = playerItem.observe(\.isPlaybackLikelyToKeepUp, options: [.new]) { [weak self] item, _ in
            if item.isPlaybackLikelyToKeepUp {
                print("✅ Buffer suffisant")
                DispatchQueue.main.async {
                    self?.isWaitingForBuffer = false
                    self?.isBuffering = false
                    
                    // Si on avait un seek en attente, on l'exécute immédiatement
                    if let pendingTime = self?.pendingSeekWhileBuffering {
                        print("🔄 Exécution du seek en attente vers \(pendingTime)s")
                        self?.pendingSeekWhileBuffering = nil
                        self?.retrySeekCount = 0
                        self?.performSeek(to: pendingTime, shouldResume: self?.shouldResumeAfterSeek ?? false)
                    }
                    // Si on devait jouer et que c'est en pause, on relance
                    else if self?.shouldResumeAfterSeek == true && self?.isPlaying == false {
                        print("▶️ Relance automatique de la lecture")
                        self?.player?.play()
                        self?.isPlaying = true
                    }
                }
            }
        }
        
        // Observateur pour détecter quand le buffer est plein (seeks plus fluides)
        if #available(iOS 13.0, *) {
            playbackBufferFullObserver = playerItem.observe(\.isPlaybackBufferFull, options: [.new]) { item, _ in
                if item.isPlaybackBufferFull {
                    print("📦 Buffer plein")
                }
            }
        }
    }
    
    private func parseM3U8Manifest(url: URL) {
        m3u8Parser?.parseManifest(url: url) { [weak self] result in
            DispatchQueue.main.async {
                switch result {
                case .success(let result):
                    self?.calculatedDuration = result.duration
                    self?.isLiveStream = result.isLive
                    print("📊 M3U8: Durée=\(result.duration)s, Live=\(result.isLive)")
                    
                    if self?.duration == 0 {
                        self?.duration = result.duration
                    }
                    
                case .failure(let error):
                    print("⚠️ Erreur parsing M3U8: \(error)")
                }
            }
        }
    }
    
    private func startDurationCheckTimer() {
        durationCheckTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
            self?.checkAndUpdateDuration()
        }
    }
    
    private func checkAndUpdateDuration() {
        guard let currentItem = player?.currentItem,
              let url = currentURL else { return }
        
        parseM3U8Manifest(url: url)
        
        if let lastRange = currentItem.seekableTimeRanges.last?.timeRangeValue {
            let seekableEnd = CMTimeGetSeconds(CMTimeAdd(lastRange.start, lastRange.duration))
            if seekableEnd > duration && seekableEnd > 0 {
                DispatchQueue.main.async {
                    self.duration = seekableEnd
                    print("📈 Durée mise à jour (seekable): \(seekableEnd)s")
                }
            }
        }
    }

    private func performInitialSeek() {
        guard !isSeekingInitial else {
            print("⏳ Seek initial déjà en cours")
            return
        }
        isSeekingInitial = true
        
        print("🔄 Début performInitialSeek - pendingResetToZero: \(pendingResetToZero), shouldAutoPlay: \(shouldAutoPlay)")
        
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [weak self] in
            guard let self = self,
                  let player = self.player,
                  let currentItem = player.currentItem else {
                print("❌ performInitialSeek: player ou item nil")
                self?.isSeekingInitial = false
                return
            }
            
            print("📊 Status du playerItem: \(currentItem.status.rawValue)")
            
            if currentItem.status == .readyToPlay {
                let effectiveDuration = max(self.duration, self.calculatedDuration)
                self.updateDuration(from: currentItem)
                
                print("📊 Durée effective: \(effectiveDuration)s")
                
                if effectiveDuration > 1.0 {
                    print("✅ Durée disponible: \(effectiveDuration)s")
                    
                    // Vérifier si on doit reset à 0
                    if self.pendingResetToZero {
                        print("🔄 EXÉCUTION DU RESET À 0 EN ATTENTE")
                        self.pendingResetToZero = false
                        
                        if self.shouldAutoPlay {
                            print("▶️ Reset à 0 avec autoplay activé")
                            self.seekAndPlay(at: .zero)
                        } else {
                            print("⏸️ Reset à 0 sans autoplay")
                            self.seekAndPause(at: .zero)
                        }
                    } else {
                        print("▶️ Démarrage normal à la position actuelle")
                        if self.shouldAutoPlay {
                            self.player?.play()
                            self.isPlaying = true
                            self.isBuffering = false
                        }
                        self.isSeekingInitial = false
                        self.isTransitioningPrograms = false
                    }
                    
                    self.hasPlaybackBeenInitiated = true
                    
                } else {
                    print("⏳ Durée insuffisante (\(effectiveDuration)s), nouvelle tentative dans 1s")
                    self.isSeekingInitial = false
                    DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) { [weak self] in
                        self?.performInitialSeek()
                    }
                }
            } else if currentItem.status == .failed {
                print("❌ PlayerItem en échec")
                self.errorMessage = "Impossible de charger la chronique"
                self.isLoading = false
                self.isSeekingInitial = false
                self.isTransitioningPrograms = false
            } else {
                print("⏳ PlayerItem pas prêt (status: \(currentItem.status.rawValue)), nouvelle tentative dans 0.5s")
                self.isSeekingInitial = false
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [weak self] in
                    self?.performInitialSeek()
                }
            }
        }
    }

    private func seekAndPlay(at time: CMTime) {
        guard let player = player else {
            isSeekingInitial = false
            return
        }
        
        print("🎯 seekAndPlay vers \(time.seconds)s")
        
        player.seek(to: time, toleranceBefore: .zero, toleranceAfter: .zero) { [weak self] finished in
            guard let self = self else { return }
            
            if finished {
                let currentTime = player.currentTime().seconds
                if currentTime >= 0 && !currentTime.isNaN && !currentTime.isInfinite {
                    print("✅ Seek réussi à \(currentTime)s, lancement de la lecture")
                    
                    if let item = player.currentItem {
                        self.updateDuration(from: item)
                    }
                    
                    self.player?.play()
                    self.isPlaying = true
                    self.isBuffering = false
                    self.isSeekingInitial = false
                    self.isTransitioningPrograms = false
                    self.hasPlaybackBeenInitiated = true
                    
                    print("✅ Lecture démarrée depuis le début")
                    
                } else {
                    print("⚠️ Position invalide après seek, nouvelle tentative")
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { [weak self] in
                        self?.seekAndPlay(at: time)
                    }
                }
            } else {
                print("❌ Seek interrompu, nouvelle tentative")
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { [weak self] in
                    self?.seekAndPlay(at: time)
                }
            }
        }
    }
    
    private func seekAndPause(at time: CMTime) {
        guard let player = player else {
            isSeekingInitial = false
            return
        }
        
        print("🔄 Exécution seekAndPause vers 0")
        
        player.seek(to: time, toleranceBefore: .zero, toleranceAfter: .zero) { [weak self] finished in
            guard let self = self else { return }
            
            if finished {
                let currentTime = player.currentTime().seconds
                if currentTime >= 0 && !currentTime.isNaN && !currentTime.isInfinite {
                    print("✅ Reset à 0 réussi à \(currentTime)s")
                    
                    if let item = player.currentItem {
                        self.updateDuration(from: item)
                    }
                    
                    self.player?.pause()
                    self.isPlaying = false
                    self.isBuffering = false
                    
                    DispatchQueue.main.async {
                        self.currentTime = 0
                        self.isSeekingInitial = false
                        self.isTransitioningPrograms = false
                        self.pendingResetToZero = false
                    }
                    
                    self.hasPlaybackBeenInitiated = true
                    
                    print("✅ Reset à 0 terminé avec succès")
                } else {
                    print("⚠️ Position invalide après reset (\(currentTime)s), nouvelle tentative")
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { [weak self] in
                        self?.seekAndPause(at: time)
                    }
                }
            } else {
                print("❌ Reset interrompu, nouvelle tentative")
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { [weak self] in
                    self?.seekAndPause(at: time)
                }
            }
        }
    }

    private func updateDuration(from item: AVPlayerItem) {
        var newDuration: TimeInterval = 0
        
        let itemDuration = item.duration.seconds
        if !itemDuration.isNaN && !itemDuration.isInfinite && itemDuration > 0 {
            newDuration = itemDuration
        }
        
        if newDuration == 0, let lastRange = item.seekableTimeRanges.last?.timeRangeValue {
            let totalSeconds = CMTimeGetSeconds(CMTimeAdd(lastRange.start, lastRange.duration))
            if !totalSeconds.isNaN && !totalSeconds.isInfinite && totalSeconds > 0 {
                newDuration = totalSeconds
            }
        }
        
        if newDuration == 0, let lastRange = item.loadedTimeRanges.last?.timeRangeValue {
            let loadedSeconds = CMTimeGetSeconds(CMTimeAdd(lastRange.start, lastRange.duration))
            if !loadedSeconds.isNaN && !loadedSeconds.isInfinite && loadedSeconds > 0 {
                newDuration = loadedSeconds
            }
        }
        
        if newDuration == 0 && calculatedDuration > 0 {
            newDuration = calculatedDuration
        }
        
        if newDuration > 0 && abs(newDuration - lastKnownDuration) > 0.1 {
            DispatchQueue.main.async {
                self.duration = newDuration
                self.lastKnownDuration = newDuration
                print("📊 Durée mise à jour: \(newDuration)s (calculée: \(self.calculatedDuration)s)")
            }
        }
    }

    @objc private func itemDidPlayToEndTime(notification: NSNotification) {
        next()
    }

    private func observePlayerItemStatus(_ playerItem: AVPlayerItem) {
        itemStatusObserver?.invalidate()
        seekableRangesObserver?.invalidate()
        loadedTimeRangesObserver?.invalidate()
        
        itemStatusObserver = playerItem.observe(\.status, options: [.new, .old]) { [weak self] item, change in
            DispatchQueue.main.async {
                guard let self = self else { return }
                
                switch item.status {
                case .readyToPlay:
                    self.updateDuration(from: item)
                    
                    let effectiveDuration = max(self.duration, self.calculatedDuration)
                    
                    if effectiveDuration > 1.0 {
                        self.isReady = true
                        self.errorMessage = nil
                        self.isLoading = false
                        
                        print("✅ PlayerItem prêt. Durée: \(effectiveDuration)s")
                        
                        if self.forceResetToZero && !self.isSeekingInitial {
                            print("🔄 Reset forcé détecté dans status observer")
                            self.forceResetToBeginning()
                        }
                        else if self.pendingResetToZero && !self.isSeekingInitial {
                            print("🔄 Exécution du reset à 0 (depuis status observer)")
                            self.performInitialSeek()
                        }
                        else if let pendingTime = self.pendingSeekTime {
                            print("⏱️ Exécution du seek en attente vers \(pendingTime)s")
                            let shouldResume = self.shouldResumeAfterSeek
                            self.pendingSeekTime = nil
                            self.performSeek(to: pendingTime, shouldResume: shouldResume)
                        }
                    } else {
                        print("⏳ Item prêt mais durée insuffisante (\(effectiveDuration)s), attente...")
                        self.isReady = false
                        self.isLoading = true
                    }
                    
                case .failed:
                    let error = item.error?.localizedDescription ?? "Erreur inconnue"
                    let fileName = self.currentURL?.lastPathComponent ?? "inconnu"
                    self.errorMessage = "Chronique indisponible pour le moment"
                    self.isLoading = false
                    self.isReady = false
                    self.isTransitioningPrograms = false
                    print("❌ PlayerItem a échoué [\(fileName)] : \(error)")
                    
                    if !(item.error?.localizedDescription.contains("404") ?? false) && !self.isRetrying {
                        self.retryPlayback(at: self.currentChronicleIndex)
                    } else {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) { [weak self] in
                            self?.next()
                        }
                    }
                    
                case .unknown:
                    print("⏳ PlayerItem status unknown")
                    
                @unknown default:
                    break
                }
            }
        }
        
        seekableRangesObserver = playerItem.observe(\.seekableTimeRanges, options: [.new]) { [weak self] item, _ in
            DispatchQueue.main.async {
                guard let self = self else { return }
                
                let oldDuration = self.duration
                self.updateDuration(from: item)
                
                if self.duration > oldDuration + 0.5 && !self.isPlaying && self.duration > 1.0 {
                    if let player = self.player, player.currentItem == item {
                        print("🔄 Durée maintenant disponible (\(self.duration)s)")
                        if self.forceResetToZero && !self.isSeekingInitial {
                            print("🔄 Reset forcé après mise à jour durée")
                            self.forceResetToBeginning()
                        }
                        else if self.pendingResetToZero && !self.isSeekingInitial {
                            print("🔄 Reset à 0 après mise à jour durée")
                            self.performInitialSeek()
                        }
                    }
                }
            }
        }
        
        loadedTimeRangesObserver = playerItem.observe(\.loadedTimeRanges, options: [.new]) { [weak self] item, _ in
            DispatchQueue.main.async {
                guard let self = self else { return }
                
                self.updateDuration(from: item)
                
                let loadedRanges = item.loadedTimeRanges
                self.loadedSegmentsCount = loadedRanges.count
                
                self.updateLoadingProgress()
            }
        }
    }

    private func retryPlayback(at index: Int) {
        guard !isRetrying else { return }
        
        if retryCount >= maxRetryCount {
            print("❌ Nombre maximum de tentatives atteint (\(maxRetryCount))")
            retryCount = 0
            isRetrying = false
            currentRetryIndex = nil
            errorMessage = "Impossible de charger la chronique après plusieurs tentatives"
            return
        }
        
        isRetrying = true
        currentRetryIndex = index
        retryCount += 1
        
        print("🔄 Tentative de reconnexion \(retryCount)/\(maxRetryCount) pour l'index \(index)...")
        
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) { [weak self] in
            guard let self = self else { return }
            
            if self.currentChronicleIndex == index {
                self.isRetrying = false
                self.playChronicle(at: index)
            } else {
                print("⏭️ Retry annulé : l'utilisateur a changé de chronique.")
                self.retryCount = 0
                self.isRetrying = false
                self.currentRetryIndex = nil
            }
        }
    }

    // MARK: - Contrôles
    func play() {
        if !hasPlaybackBeenInitiated {
            hasPlaybackBeenInitiated = true
        }
        
        if player?.status == .failed || player?.currentItem?.status == .failed {
            playChronicle(at: currentChronicleIndex)
        } else {
            player?.play()
            self.isPlaying = true
            self.isBuffering = false
        }
    }
    
    func pause() {
        player?.pause()
        self.isPlaying = false
        self.isBuffering = false
    }
    
    func togglePlayPause() {
        if isPlaying {
            pause()
        } else {
            play()
        }
    }
    
    func next() {
        if currentChronicleIndex < programs.count - 1 {
            playChronicle(at: currentChronicleIndex + 1)
        }
    }
    
    func previous() {
        if currentChronicleIndex > 0 {
            playChronicle(at: currentChronicleIndex - 1)
        }
    }
    
    // MARK: - Boutons de navigation rapide
    
    func skipBackward() {
        let newTime = max(currentTime - 15, 0)
        performSkip(to: newTime, hapticFeedback: true)
    }
    
    func skipForward() {
        let effectiveDuration = safeDuration
        guard effectiveDuration > 0 else { return }
        
        let newTime = min(currentTime + 30, effectiveDuration)
        performSkip(to: newTime, hapticFeedback: true)
    }
    
    private func performSkip(to time: TimeInterval, hapticFeedback: Bool = true) {
        let wasPlaying = isPlaying
        
        if hapticFeedback && !isTestMode {
            provideHapticFeedback()
        }
        
        if !isTestMode {
            objectWillChange.send()
        }
        
        // Sauvegarder l'état pour la reprise
        shouldResumeAfterSeek = wasPlaying
        
        // Annuler tout seek en attente
        seekTimer?.invalidate()
        
        // Mettre à jour l'état isPlaying en fonction de ce qu'on veut
        if wasPlaying && !isTestMode {
            // On était en train de jouer, on met en pause temporairement
            player?.pause()
            self.isPlaying = false
            self.isBuffering = true // Indique qu'on attend le chargement
        }
        
        // Effectuer le seek immédiatement
        if isTestMode {
            self.currentTime = time
        } else {
            performSeek(to: time, shouldResume: wasPlaying)
        }
        
        print("⏩ Skip to: \(formatTime(time)) (wasPlaying: \(wasPlaying))")
    }
    
    private func provideHapticFeedback() {
        let generator = UIImpactFeedbackGenerator(style: .medium)
        generator.impactOccurred()
    }
    
    func beginSeeking() {
        isSeeking = true
        shouldResumeAfterSeek = isPlaying
        if isPlaying {
            player?.pause()
            self.isPlaying = false
        }
    }
    
    func seekUpdate(to time: TimeInterval) {
        guard time.isFinite && !time.isNaN && time >= 0 else { return }
        currentTime = time
    }
    
    func endSeeking(to time: TimeInterval) {
        // Quand on relâche le slider, on met en buffering en attendant le seek
        if shouldResumeAfterSeek {
            self.isBuffering = true
        }
        performSeek(to: time, shouldResume: shouldResumeAfterSeek)
    }
    
    // Méthode unifiée pour tous les seeks avec gestion optimisée du buffer
    private func performSeek(to time: TimeInterval, shouldResume: Bool) {
        if isTestMode {
            self.currentTime = time
            self.isSeeking = false
            return
        }
        guard let player = player, time.isFinite && !time.isNaN && time >= 0 else {
            isSeeking = false
            return
        }
        
        // Éviter les seeks trop rapprochés
        let now = Date().timeIntervalSince1970
        if now - lastSeekTime < 0.1 && isSeekPending {
            print("⏳ Seek trop rapproché, ignoré")
            return
        }
        lastSeekTime = now
        isSeekPending = true
        
        // Vérifier que la durée est valide
        let effectiveDuration = safeDuration
        guard effectiveDuration > 0 else {
            print("⚠️ Durée non disponible pour le seek")
            isSeeking = false
            isSeekPending = false
            return
        }
        
        // S'assurer que le temps est dans les limites
        let clampedTime = min(max(time, 0), effectiveDuration)
        
        // Vérifier si le player est prêt
        if player.currentItem?.status != .readyToPlay {
            print("⏳ Player pas prêt, mise en attente du seek vers \(clampedTime)s")
            pendingSeekTime = clampedTime
            shouldResumeAfterSeek = shouldResume
            isSeeking = false
            isSeekPending = false
            return
        }
        
        // Vérifier si la zone est déjà chargée (pour seeks plus rapides)
        let isTimeLoaded = isTimeLoadedInCache(clampedTime)
        
        let cmTime = CMTime(seconds: clampedTime, preferredTimescale: 600)
        
        print("🎯 PerformSeek vers \(clampedTime)s, chargé: \(isTimeLoaded), reprise: \(shouldResume)")
        
        // Tolérances adaptées selon si la zone est chargée
        let tolerance: CMTime = isTimeLoaded ? .zero : CMTime(seconds: 0.5, preferredTimescale: 600)
        
        player.seek(to: cmTime, toleranceBefore: tolerance, toleranceAfter: tolerance) { [weak self] finished in
            guard let self = self else { return }
            
            DispatchQueue.main.async {
                self.isSeekPending = false
                
                if finished {
                    print("✅ Seek terminé avec succès vers \(clampedTime)s")
                    
                    // Réinitialiser le compteur de tentatives
                    self.retrySeekCount = 0
                    
                    // Mettre à jour le temps courant
                    self.currentTime = clampedTime
                    
                    // Vérifier si la zone est chargée après le seek
                    if !self.isTimeLoadedInCache(clampedTime) {
                        print("⏳ Zone non chargée après seek, buffer vide")
                        self.isWaitingForBuffer = true
                        self.isBuffering = true
                        
                        // On garde le shouldResume pour quand le buffer sera prêt
                        self.shouldResumeAfterSeek = shouldResume
                        
                        // Si on devait reprendre, on attend que le buffer soit prêt
                        if shouldResume {
                            self.pendingSeekWhileBuffering = clampedTime
                            // On s'assure que le player est en pause
                            player.pause()
                            self.isPlaying = false
                        }
                    } else {
                        // Zone chargée, on peut reprendre immédiatement
                        self.isWaitingForBuffer = false
                        self.isBuffering = false
                        
                        if shouldResume {
                            print("▶️ Reprise immédiate de la lecture")
                            player.play()
                            self.isPlaying = true
                        } else {
                            self.isPlaying = false
                        }
                    }
                    
                    self.isSeeking = false
                    
                } else {
                    print("❌ Seek interrompu, tentative \(self.retrySeekCount + 1)/\(self.maxRetrySeekCount)")
                    
                    if self.retrySeekCount < self.maxRetrySeekCount {
                        self.retrySeekCount += 1
                        // Réessayer avec un délai progressif
                        let delay = 0.1 * Double(self.retrySeekCount)
                        DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
                            self.performSeek(to: clampedTime, shouldResume: shouldResume)
                        }
                    } else {
                        print("❌ Nombre maximum de tentatives de seek atteint")
                        self.retrySeekCount = 0
                        self.isSeeking = false
                        self.isBuffering = false
                        
                        // En cas d'échec, on essaie de remettre la lecture dans un état cohérent
                        if shouldResume {
                            player.play()
                            self.isPlaying = true
                        } else {
                            self.isPlaying = false
                        }
                    }
                }
            }
        }
    }
    
    // Vérifie si un temps donné est chargé dans le cache
    private func isTimeLoadedInCache(_ time: TimeInterval) -> Bool {
        let cmTime = CMTime(seconds: time, preferredTimescale: 600)
        
        for timeRange in loadedTimeRangesCache {
            let start = timeRange.start.seconds
            let end = start + timeRange.duration.seconds
            
            if time >= start && time <= end {
                return true
            }
        }
        return false
    }
    
    // Méthode publique pour compatibilité
    func seek(to time: TimeInterval) {
        beginSeeking()
        endSeeking(to: time)
    }
    
    func formatTime(_ time: TimeInterval) -> String {
        guard time.isFinite && !time.isNaN && time >= 0 else {
            return "00:00"
        }
        
        let displayTime = time
        
        let totalSeconds = Int(displayTime)
        let hours = totalSeconds / 3600
        let minutes = (totalSeconds % 3600) / 60
        let seconds = totalSeconds % 60
        
        if hours > 0 {
            return String(format: "%02d:%02d:%02d", hours, minutes, seconds)
        } else {
            return String(format: "%02d:%02d", minutes, seconds)
        }
    }
    
    var safeDuration: Double {
        let effectiveDuration = max(duration, calculatedDuration)
        return effectiveDuration.isFinite && !effectiveDuration.isNaN && effectiveDuration > 0 ? effectiveDuration : 0
    }
    
    var progress: Double {
        guard safeDuration > 0 else { return 0 }
        return min(max(currentTime / safeDuration, 0), 1)
    }
    
    deinit {
        if let timeObserver = timeObserver {
            player?.removeTimeObserver(timeObserver)
        }
        itemStatusObserver?.invalidate()
        seekableRangesObserver?.invalidate()
        loadedTimeRangesObserver?.invalidate()
        playbackBufferEmptyObserver?.invalidate()
        playbackLikelyToKeepUpObserver?.invalidate()
        playbackBufferFullObserver?.invalidate()
        timeControlStatusObserver?.invalidate()
        rateObserver?.invalidate()
        durationCheckTimer?.invalidate()
        assetDurationTimer?.invalidate()
        seekTimer?.invalidate()
        NotificationCenter.default.removeObserver(self)
    }
}

// MARK: - M3U8 Parser
class M3U8Parser {
    private var currentTask: URLSessionDataTask?
    private var refreshTimer: Timer?
    private var parsedSegments: [M3U8Segment] = []
    private var onUpdate: ((TimeInterval) -> Void)?
    
    struct M3U8Segment {
        let duration: TimeInterval
        let uri: String
        let sequence: Int
    }
    
    func parseManifest(url: URL, completion: @escaping (Result<(duration: TimeInterval, isLive: Bool), Error>) -> Void) {
        currentTask?.cancel()
        
        var request = URLRequest(url: url)
        request.setValue("audio/mpegurl", forHTTPHeaderField: "Accept")
        request.setValue("identity", forHTTPHeaderField: "Accept-Encoding")
        
        currentTask = URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            if let error = error {
                DispatchQueue.main.async {
                    completion(.failure(error))
                }
                return
            }
            
            guard let data = data, let manifestString = String(data: data, encoding: .utf8) else {
                DispatchQueue.main.async {
                    completion(.failure(NSError(domain: "M3U8Parser", code: -1, userInfo: [NSLocalizedDescriptionKey: "Données invalides"])))
                }
                return
            }
            
            let totalDuration = self?.parseManifestContent(manifestString) ?? 0
            let isLive = !manifestString.contains("#EXT-X-ENDLIST")
            
            DispatchQueue.main.async {
                completion(.success((duration: totalDuration, isLive: isLive)))
            }
            
            if isLive {
                self?.startPeriodicRefresh(url: url, completion: completion)
            }
        }
        
        currentTask?.resume()
    }
    
    private func parseManifestContent(_ content: String) -> TimeInterval {
        let lines = content.components(separatedBy: .newlines)
        var totalDuration: TimeInterval = 0
        var newSegments: [M3U8Segment] = []
        var currentSequence = 0
        
        for line in lines {
            if line.hasPrefix("#EXTINF:") {
                let durationString = line.dropFirst(8)
                if let commaIndex = durationString.firstIndex(of: ",") {
                    let duration = Double(durationString[..<commaIndex]) ?? 0
                    totalDuration += duration
                    
                    if let uriLineIndex = lines.firstIndex(of: line)?.advanced(by: 1),
                       uriLineIndex < lines.count {
                        let uri = lines[uriLineIndex]
                        if !uri.hasPrefix("#") {
                            let segment = M3U8Segment(duration: duration, uri: uri, sequence: currentSequence)
                            newSegments.append(segment)
                            currentSequence += 1
                        }
                    }
                }
            } else if line.hasPrefix("#EXT-X-MEDIA-SEQUENCE:") {
                if let sequenceString = line.split(separator: ":").last {
                    currentSequence = Int(sequenceString) ?? 0
                }
            }
        }
        
        if !newSegments.isEmpty {
            parsedSegments = newSegments
        }
        
        print("📊 M3U8: \(newSegments.count) segments, durée totale: \(totalDuration)s")
        return totalDuration
    }
    
    private func startPeriodicRefresh(url: URL, completion: @escaping (Result<(duration: TimeInterval, isLive: Bool), Error>) -> Void) {
        refreshTimer?.invalidate()
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 6.0, repeats: true) { [weak self] _ in
            self?.parseManifest(url: url, completion: completion)
        }
    }
    
    deinit {
        currentTask?.cancel()
        refreshTimer?.invalidate()
    }
}
