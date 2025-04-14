//
//  ViewModel.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 1/4/25.
//

import Foundation
import FirebaseAuth
import FirebaseFirestore

@Observable
final class ViewModel: NSObject {
    var allNews = [News]()
    var filteredNews = [NeutralNews]()
    var groupsOfNews = [[News]]()
    var neutralNews = [NeutralNews]()
    private var currentElement: String = ""
    private var currentElementValue: String = ""
    private var currentTitle: String = ""
    private var currentDescription: String = ""
    private var currentCategories: [String] = []
    private var currentImageUrl: String = ""
    private var currentLink: String = ""
    private var currentPubDate: String = ""
    private var currentNeutralScore: Int = 0
    private var currentMedium: Media?
    
    var mediaFilter: Set<Media> = []
    var categoryFilter: Set<Category> = []
    var isAnyFilterEnabled: Bool {
        !mediaFilter.isEmpty || !categoryFilter.isEmpty
    }
    
    override init() {
        super.init()
        fetchNeutralNewsFromFirestore()
        fetchNewsFromFirestore()
    }
    
    func fetchNeutralNewsFromFirestore() {
        let db = Firestore.firestore()
        db.collection("neutral_news").getDocuments { snapshot, error in
            if let error = error {
                print("Error fetching neutral news: \(error.localizedDescription)")
                return
            }
            
            guard let documents = snapshot?.documents else {
                print("No neutral news found in Firestore")
                return
            }
            
            let fetchedNeutralNews = documents.compactMap { doc -> NeutralNews? in
                let data = doc.data()
                guard let neutralTitle = data["neutral_title"] as? String,
                      let neutralDescription = data["neutral_description"] as? String,
                      let group = data["group_number"] as? Int,
                      let category = data["category"] as? String
//                      let imageUrl = data["imageUrl"] as? String?,
//                      let pubDate = data["pubDate"] as? String
                else {
                    print("Error parsing news document")
                    return nil
                }
                
                return NeutralNews(
                    neutralTitle: neutralTitle,
                    neutralDescription: neutralDescription,
                    category: category,
                    imageUrl: /*imageUrl ??*/ "",
//                    pubDate: pubDate,
                    group: group
                )
            }
            
            DispatchQueue.main.async {
                self.neutralNews = fetchedNeutralNews
                self.filterGroupedNews()
                self.applyFilters()
            }
        }
    }
    
    func getRelatedNews(from neutralNews: NeutralNews) -> [News] {
        groupsOfNews.first(where: { $0.first?.group == neutralNews.group }) ?? []
    }
    
    func fetchNewsFromFirestore() {
        let db = Firestore.firestore()
        db.collection("news").getDocuments { snapshot, error in
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
                      let imageUrl = data["imageUrl"] as? String?,
                      let link = data["link"] as? String,
                      let pubDate = data["pubDate"] as? String,
                      let neutralScore = data["neutral_score"] as? Int?,
                      let sourceMediumRaw = data["sourceMedium"] as? String,
                      let sourceMedium = Media(rawValue: sourceMediumRaw) else {
                    print("Error parsing news document")
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
                self.applyFilters()
            }
        }
    }
    
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
        if mediaFilter.isEmpty && categoryFilter.isEmpty {
            filteredNews = neutralNews
            return
        }
        
        filteredNews = neutralNews.filter { news in
//            let matchesMedia = mediaFilter.isEmpty || mediaFilter.contains(news.sourceMedium)
            let matchesCategory = categoryFilter.isEmpty || categoryFilter.contains { category in
                news.category.normalized() == category.rawValue.normalized()
            }
            
            return /*matchesMedia &&*/ matchesCategory
        }
    }
    
    func allCategories() -> Set<String> {
        Set(allNews.map(\.category))
    }
}

extension String {
    func toDate() -> Date? {
        let dateFormatter = DateFormatter()
        dateFormatter.locale = Locale(identifier: "en_US_POSIX")
        dateFormatter.dateFormat = "EEE, dd MMM yyyy HH:mm:ss Z"
        return dateFormatter.date(from: self)
    }
}
