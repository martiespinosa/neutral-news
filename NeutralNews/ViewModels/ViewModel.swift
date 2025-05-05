//
//  ViewModel.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 1/4/25.
//

import Foundation
import FirebaseAuth
import FirebaseFirestore
import SwiftUI

@Observable
final class ViewModel: NSObject {
    // MARK: - Properties
    var allNews = [News]()
    var filteredNews = [NeutralNews]()
    
    var todayNews = Set<NeutralNews>()
    var yesterdayNews = Set<NeutralNews>()
    var threeDaysAgoNews = Set<NeutralNews>()
    var fourDaysAgoNews = Set<NeutralNews>()
    var fiveDaysAgoNews = Set<NeutralNews>()
    var sixDaysAgoNews = Set<NeutralNews>()
    var sevenDaysAgoNews = Set<NeutralNews>()
    
    var lastExecutionDate: Date?
    
    // MARK: - UI State
    var daySelected: DayInfo = .today {
        didSet {
            updateNewsToShow(withFilters: true)
        }
    }
    var newsToShow = [NeutralNews]()
    var isLoadingNeutralNews = false
    
    // MARK: - Search and Filter
    var searchText: String = "" {
        didSet {
            if searchText != oldValue {
                applyFilters()
            }
        }
    }
    var mediaFilter: Set<Media> = []
    var categoryFilter: Set<Category> = []
    var isAnyFilterEnabled: Bool {
        !mediaFilter.isEmpty || !categoryFilter.isEmpty
    }
    
    // MARK: - Data Collections
    var groupsOfNews = [[News]]()
    var neutralNews = [NeutralNews]()
    
    // MARK: - Computed Properties
    var lastSevenDays: [DayInfo] {
        let calendar = Calendar.current
        let dayFormatter = DateFormatter()
        let monthFormatter = DateFormatter()
        
        dayFormatter.locale = Locale(identifier: "es_ES")
        dayFormatter.dateFormat = "EEEE"
        
        monthFormatter.locale = Locale(identifier: "es_ES")
        monthFormatter.dateFormat = "MMMM"
        
        return (0..<7).compactMap { offset in
            guard let date = calendar.date(byAdding: .day, value: -offset, to: .now) else { return nil }
            
            let dayNumber = calendar.component(.day, from: date)
            let monthName = monthFormatter.string(from: date)
            
            let dayName: String
            switch offset {
            case 0: dayName = "Hoy"
            case 1: dayName = "Ayer"
            default: dayName = dayFormatter.string(from: date).capitalized
            }
            
            return DayInfo(
                dayName: dayName,
                dayNumber: dayNumber,
                monthName: monthName,
                date: date
            )
        }
    }
    
    var newsByDay: [DayInfo: Set<NeutralNews>] {
        let allNews = [
            todayNews,
            yesterdayNews,
            threeDaysAgoNews,
            fourDaysAgoNews,
            fiveDaysAgoNews,
            sixDaysAgoNews,
            sevenDaysAgoNews
        ]
        return Dictionary(uniqueKeysWithValues: zip(lastSevenDays, allNews))
    }
    
    var daySelectedNews: [NeutralNews] {
        let calendar = Calendar.current
        
        return neutralNews.filter { news in
            guard let newsDate = news.date else { return false }
            return calendar.isDate(newsDate, inSameDayAs: daySelected.date)
        }.sorted { ($0.date ?? Date.distantPast) > ($1.date ?? Date.distantPast) }
    }
    
    // MARK: - Initialization
    override init() {
        super.init()
        fetchNeutralNewsFromFirestore()
        fetchNewsFromFirestore()
        setupDayChangeTimer()
    }
    
    // MARK: - Firestore Methods
    func fetchNeutralNewsFromFirestore() {
        isLoadingNeutralNews = true
        
        let db = Firestore.firestore()
        db.collection("neutral_news").getDocuments { [weak self] snapshot, error in
            guard let self = self else { return }
            
            if let error = error {
                print("Error fetching neutral news: \(error.localizedDescription)")
                self.isLoadingNeutralNews = false
                return
            }
            
            guard let documents = snapshot?.documents else {
                print("No neutral news found in Firestore")
                self.isLoadingNeutralNews = false
                return
            }
            
            let fetchedNeutralNews = documents.compactMap { doc -> NeutralNews? in
                let data = doc.data()
                let docID = doc.documentID
                
                guard let neutralTitle = data["neutral_title"] as? String,
                      let neutralDescription = data["neutral_description"] as? String,
                      let category = data["category"] as? String,
                      let relevance = data["relevance"] as? Int?,
                      let imageUrl = data["image_url"] as? String?,
                      let imageMedium = data["image_medium"] as? String?,
                      let date = data["date"] as? Timestamp?,
                      let createdAt = data["created_at"] as? Timestamp,
                      let updatedAt = data["updated_at"] as? Timestamp,
                      let group = data["group"] as? Int
                else {
                    print("Error parsing neutral news document: \(docID)")
                    return nil
                }
                
                return NeutralNews(
                    neutralTitle: neutralTitle,
                    neutralDescription: neutralDescription,
                    category: category,
                    relevance: relevance,
                    imageUrl: imageUrl,
                    imageMedium: imageMedium,
                    date: date?.dateValue(),
                    createdAt: createdAt.dateValue(),
                    updatedAt: updatedAt.dateValue(),
                    group: group
                )
            }
            
            DispatchQueue.main.async {
                self.neutralNews = fetchedNeutralNews.sorted { $0.createdAt > $1.createdAt }
                self.classifyNewsByDate()
                
                if !self.allNews.isEmpty {
                    self.updateNewsToShow(withFilters: false)
                    self.filterGroupedNews()
                }
                
                self.isLoadingNeutralNews = false
            }
        }
    }
    
    func fetchNewsFromFirestore() {
        let db = Firestore.firestore()
        db.collection("news").getDocuments { [weak self] snapshot, error in
            guard let self = self else { return }
            
            if let error = error {
                print("Error fetching news: \(error.localizedDescription)")
                return
            }
            
            guard let documents = snapshot?.documents else {
                print("No news found in Firestore")
                return
            }
            
            let fetchedNews = documents.compactMap { doc -> News? in
                let data = doc.data()
                guard let title = data["title"] as? String,
                      let description = data["description"] as? String,
                      let group = data["group"] as? Int?,
                      let category = data["category"] as? String?,
                      let imageUrl = data["image_url"] as? String?,
                      let link = data["link"] as? String,
                      let pubDate = data["pub_date"] as? String,
                      let neutralScore = data["neutral_score"] as? Int?,
                      let sourceMediumRaw = data["source_medium"] as? String,
                      let sourceMedium = Media(rawValue: sourceMediumRaw)
                else {
                    if let sourceMediumRaw = data["source_medium"] as? String {
                        print("Error parsing news document from \(sourceMediumRaw)")
                    }
                    return nil
                }
                
                return News(
                    title: title,
                    description: description,
                    category: category ?? "",
                    imageUrl: imageUrl ?? "",
                    link: link,
                    pubDate: pubDate,
                    sourceMedium: sourceMedium,
                    neutralScore: neutralScore,
                    group: group
                )
            }
            
            DispatchQueue.main.async {
                self.allNews = fetchedNews
                self.filterGroupedNews()
                
                if !self.neutralNews.isEmpty {
                    self.updateNewsToShow(withFilters: false)
                }
            }
        }
    }
    
    // MARK: - News Processing
    func getRelatedNews(from neutralNews: NeutralNews) -> [News] {
        groupsOfNews.first(where: { $0.first?.group == neutralNews.group }) ?? []
    }
    
    func filterGroupedNews() {
        let groupedNews = Dictionary(grouping: allNews.compactMap { $0.group != nil ? $0 : nil }, by: { $0.group! })
        let filteredGroups = groupedNews.filter { $0.value.count > 1 && $0.key != -1}
        
        let sortedGroups = filteredGroups.sorted { group1, group2 in
            guard let latestNews1 = group1.value.first, let latestNews2 = group2.value.first else {
                return false
            }
            return latestNews1.pubDate > latestNews2.pubDate
        }
        
        groupsOfNews = sortedGroups.map { $0.value }
    }
    
    func setupDayChangeTimer() {
        let calendar = Calendar.current
        var components = DateComponents()
        components.hour = 0
        components.minute = 0
        components.second = 0
        
        guard let tomorrow = calendar.nextDate(after: Date(), matching: components, matchingPolicy: .nextTime) else {
            print("Error calculando la próxima medianoche")
            return
        }
        
        let timeInterval = tomorrow.timeIntervalSince(Date())
        print("Próximo cambio de día en \(Int(timeInterval)) segundos")
        
        Timer.scheduledTimer(withTimeInterval: timeInterval, repeats: false) { [weak self] _ in
            print("¡Es medianoche! Actualizando clasificación de noticias...")
            self?.handleDayChange()
            self?.setupDayChangeTimer()
        }
    }

    func handleDayChange() {
        sevenDaysAgoNews.removeAll()
        sixDaysAgoNews = sevenDaysAgoNews
        fiveDaysAgoNews = sixDaysAgoNews
        fourDaysAgoNews = fiveDaysAgoNews
        threeDaysAgoNews = fourDaysAgoNews
        yesterdayNews = todayNews
        todayNews.removeAll()
        
        lastExecutionDate = Date()
        
        classifyNewsByDate()
        
        if daySelected.dayName == "Hoy" || daySelected.dayName == "Ayer" || lastSevenDays.contains(daySelected) {
            updateNewsToShow(withFilters: true)
        }
    }
    
    func classifyNewsByDate() {
        let currentDate = Date()
        let calendar = Calendar.current
        
        let shouldChangeDay = isAnotherDay(currentDate: currentDate)
        
        if shouldChangeDay {
            todayNews.removeAll()
            yesterdayNews.removeAll()
            threeDaysAgoNews.removeAll()
            fourDaysAgoNews.removeAll()
            fiveDaysAgoNews.removeAll()
            sixDaysAgoNews.removeAll()
            sevenDaysAgoNews.removeAll()
            
            lastExecutionDate = currentDate
        }
        
        for news in neutralNews {
            guard let newsDate = news.date else {
                continue
            }
            
            guard let daysOfDifference = calendar.dateComponents([.day], from: newsDate, to: currentDate).day else {
                continue
            }
            
            switch daysOfDifference {
            case 0:
                todayNews.insert(news)
            case 1:
                yesterdayNews.insert(news)
            case 2:
                threeDaysAgoNews.insert(news)
            case 3:
                fourDaysAgoNews.insert(news)
            case 4:
                fiveDaysAgoNews.insert(news)
            case 5:
                sixDaysAgoNews.insert(news)
            case 6:
                sevenDaysAgoNews.insert(news)
            default:
                break
            }
        }
    }
    
    func isAnotherDay(currentDate: Date) -> Bool {
        guard let lastDate = lastExecutionDate else {
            return true
        }
        
        let calendar = Calendar.current
        let isSameDay = calendar.isDate(lastDate, inSameDayAs: currentDate)
        return !isSameDay
    }
    
    // MARK: - UI Methods
    func changeDay(to dayInfo: DayInfo) {
        if daySelected != dayInfo {
            daySelected = dayInfo
        }
    }
    
    func updateNewsToShow(withFilters: Bool) {
        if withFilters {
            applyFilters()
        } else {
            newsToShow = daySelectedNews
        }
    }
    
    // MARK: - Filtering Methods
    func filterByMedium(_ medium: Media) {
        if mediaFilter.contains(medium) {
            mediaFilter.remove(medium)
        } else {
            mediaFilter.insert(medium)
        }
        applyFilters()
    }
    
    func filterByCategory(_ category: Category) {
        if categoryFilter.contains(category) {
            categoryFilter.remove(category)
        } else {
            categoryFilter.insert(category)
        }
        applyFilters()
    }
    
    func applyFilters() {
        var newsToFilter = daySelectedNews
        
        if !mediaFilter.isEmpty || !categoryFilter.isEmpty {
            newsToFilter = newsToFilter.filter { news in
                let matchesCategory = categoryFilter.isEmpty || categoryFilter.contains { category in
                    news.category.normalized() == category.rawValue.normalized()
                }
                return matchesCategory
            }
        }
        
        if !searchText.isEmpty {
            let normalizedQuery = searchText.normalizedSearchString()
            newsToFilter = newsToFilter.filter {
                $0.neutralTitle.normalizedSearchString().contains(normalizedQuery) ||
                $0.neutralDescription.normalizedSearchString().contains(normalizedQuery)
            }
        }
        
        newsToShow = newsToFilter.sorted { ($0.date ?? Date.distantPast) > ($1.date ?? Date.distantPast) }
    }
    
    func clearFilters() {
        mediaFilter.removeAll()
        categoryFilter.removeAll()
        applyFilters()
    }
    
    func allCategories() -> Set<String> {
        Set(allNews.map(\.category))
    }
}

// MARK: - Authentication Extension
extension ViewModel {
    func authenticateAnonymously() {
        Auth.auth().signInAnonymously { authResult, error in
            if let error = error {
                print("Error de autenticación: \(error.localizedDescription)")
                return
            }
            
            guard let user = authResult?.user else {
                print("No se obtuvo un usuario anónimo válido")
                return
            }
            
            user.getIDToken { token, error in
                if let error = error {
                    print("Error al obtener el token: \(error.localizedDescription)")
                    return
                }
                
                guard token != nil else {
                    print("No se pudo obtener un token válido")
                    return
                }
            }
        }
    }
}

// MARK: - String Extensions
extension String {
    func normalized() -> String {
        folding(options: [.diacriticInsensitive, .caseInsensitive], locale: .current)
    }
    
    func normalizedSearchString() -> String {
        folding(options: [.diacriticInsensitive, .caseInsensitive], locale: .current)
            .replacingOccurrences(of: "[^a-zA-Z0-9\\s]", with: "", options: .regularExpression)
    }
    
    func toDate() -> Date? {
        let dateFormatter = DateFormatter()
        dateFormatter.locale = Locale(identifier: "en_US_POSIX")
        dateFormatter.dateFormat = "EEE, dd MMM yyyy HH:mm:ss Z"
        return dateFormatter.date(from: self)
    }
}

// MARK: - Image Processing
@MainActor
func getDominantColor(from urlString: String?) async -> Color {
    guard let urlString = urlString, let url = URL(string: urlString) else { return .gray }
    
    do {
        let (data, _) = try await URLSession.shared.data(from: url)
        guard let image = UIImage(data: data), let cgImage = image.cgImage else { return .gray }
        
        let width = 10, height = 10
        let context = CGContext(
            data: nil,
            width: width,
            height: height,
            bitsPerComponent: 8,
            bytesPerRow: width * 4,
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        )
        
        guard let context = context else { return .gray }
        context.draw(cgImage, in: CGRect(x: 0, y: 0, width: width, height: height))
        
        guard let data = context.data else { return .gray }
        
        var r = 0, g = 0, b = 0
        let pixelCount = width * height
        
        for i in stride(from: 0, to: pixelCount * 4, by: 4) {
            r += Int(data.load(fromByteOffset: i, as: UInt8.self))
            g += Int(data.load(fromByteOffset: i + 1, as: UInt8.self))
            b += Int(data.load(fromByteOffset: i + 2, as: UInt8.self))
        }
        
        return Color(red: Double(r) / Double(255 * pixelCount),
                     green: Double(g) / Double(255 * pixelCount),
                     blue: Double(b) / Double(255 * pixelCount))
    } catch {
        return .gray
    }
}
