//
//  ViewModel.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 1/4/25.
//

import Foundation

@Observable
final class ViewModel: NSObject {
    var allNews = [News]()
    var filteredNews = [News]()
    private var currentElement: String = ""
    private var currentElementValue: String = ""
    private var currentTitle: String = ""
    private var currentDescription: String = ""
    private var currentCategories: [String] = []
    private var currentImageUrl: String = ""
    private var currentLink: String = ""
    private var currentPubDate: String = ""
    private var currentMedium: Media?
    
    var mediaFilter: Set<Media> = []
    var categoryFilter: Set<Category> = []
    var isAnyFilterEnabled: Bool {
        !mediaFilter.isEmpty || !categoryFilter.isEmpty
    }
    
    /// Carga los datos desde los RSS, realiza el parseo del XML y lo prepara para enviarse al backend.
    func loadData() async {
        allNews.removeAll()
        
        for medium in Media.allCases {
            guard let url = URL(string: medium.pressMedia.link) else {
                print("Invalid URL")
                continue
            }
            
            self.currentMedium = medium
            
            do {
                let (data, _) = try await URLSession.shared.data(from: url)
                parseXML(data: data, for: medium)
            } catch {
                print("Error fetching RSS feed: \(error.localizedDescription)")
            }
        }
        
        applyFilters()
    }
    
    /// Parsear el XML y llenar el arreglo de noticias.
    private func parseXML(data: Data, for medium: Media) {
        let parser = XMLParser(data: data)
        parser.delegate = self
        if parser.parse() {
            print("Parsed \(allNews.count) news for \(medium).")
        } else {
            print("Failed to parse XML for \(medium).")
        }
    }
    
    /// Función para enviar las noticias al backend.
    func sendNewsToBackend() async {
        // Aquí ya no necesitamos convertir a JSON, solo pasamos las noticias al backend.
        do {
            let newsData = try JSONEncoder().encode(allNews) // Codifica las noticias en formato JSON
            
            // Asegúrate de usar la URL del endpoint correcto de tu backend.
            guard let url = URL(string: "http://127.0.0.1:5001/neutralnews-ca548/us-central1/procesar_noticias") else {
                print("URL incorrecta")
                return
            }
            
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = newsData
            
            // Realiza la solicitud HTTP
            let (data, response) = try await URLSession.shared.data(for: request)
            
            // Manejo de la respuesta del servidor
            if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 {
                if let jsonResponse = try? JSONDecoder().decode([News].self, from: data) {
                    // Actualiza las noticias agrupadas
                    self.allNews = jsonResponse
                    print("Noticias agrupadas: \(self.allNews)")
                } else {
                    print("Error al decodificar la respuesta.")
                }
            } else {
                print("Error en la respuesta del servidor.")
            }
            
        } catch {
            print("Error al enviar las noticias: \(error.localizedDescription)")
        }
    }
    
}

extension ViewModel: XMLParserDelegate {
    func parser(_ parser: XMLParser, didStartElement elementName: String, namespaceURI: String?, qualifiedName: String?, attributes attributeDict: [String : String] = [:]) {
        currentElement = elementName
        currentElementValue = ""
        
        if currentElement == "item" {
            currentTitle = ""
            currentDescription = ""
            currentCategories = []
            currentImageUrl = ""
            currentLink = ""
            currentPubDate = ""
        }
        
        if elementName == "media:content", let url = attributeDict["url"] {
            currentImageUrl = url
        }
    }
    
    func parser(_ parser: XMLParser, foundCharacters string: String) {
        if currentElement == "category" {
            currentElementValue += string
        } else {
            switch currentElement {
            case "title":
                currentTitle += string
            case "description":
                currentDescription += string
            case "link":
                currentLink += string
            case "pubDate":
                currentPubDate += string
            default:
                break
            }
        }
    }
    
    func parser(_ parser: XMLParser, didEndElement elementName: String, namespaceURI: String?, qualifiedName: String?) {
        if elementName == "category" {
            let category = currentElementValue.trimmingCharacters(in: .whitespacesAndNewlines)
            if !category.isEmpty {
                currentCategories.append(category)
            }
        }
        
        if elementName == "item", let medium = currentMedium {
            let validCategory = Category.allCases.first { category in
                let normalizedCategory = category.rawValue.normalized()
                return currentCategories.contains { newsCategory in
                    newsCategory.normalized() == normalizedCategory
                }
            }
            
            let finalCategory = validCategory ?? .sinCategoria
            
            let newsItem = News(
                title: currentTitle.trimmingCharacters(in: .whitespacesAndNewlines),
                description: currentDescription.trimmingCharacters(in: .whitespacesAndNewlines),
                category: finalCategory.rawValue,
                imageUrl: currentImageUrl,
                link: currentLink.trimmingCharacters(in: .whitespacesAndNewlines),
                pubDate: currentPubDate.trimmingCharacters(in: .whitespacesAndNewlines),
                sourceMedium: medium
            )
            
            if !allNews.contains(where: { $0.link == newsItem.link }) {
                allNews.append(newsItem)
            }
        }
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
    
    private func applyFilters() {
        if mediaFilter.isEmpty && categoryFilter.isEmpty {
            filteredNews = allNews
            return
        }
        
        filteredNews = allNews.filter { news in
            let matchesMedia = mediaFilter.isEmpty || mediaFilter.contains(news.sourceMedium)
            let matchesCategory = categoryFilter.isEmpty || categoryFilter.contains(Category(rawValue: news.category) ?? .sinCategoria)
            
            return matchesMedia && matchesCategory
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
