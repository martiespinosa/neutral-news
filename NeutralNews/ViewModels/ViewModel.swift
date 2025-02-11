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
    
    /// Loads data by fetching the RSS feed for each media item and parsing the XML data asynchronously.
    /// This function iterates through all available media types, fetches the data asynchronously,
    /// and processes it using the `parseXML` function.
    /// - Note: The function handles invalid URLs and errors during the data fetching process.
    /// - Important: If some RSS feeds fail to fetch, the process will continue for other media items without terminating.
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
    
    /// Parses the provided XML data and processes it using the XMLParser.
    /// - Parameter data: The XML data to be parsed.
    private func parseXML(data: Data, for medium: Media) {
        let parser = XMLParser(data: data)
        parser.delegate = self
        if parser.parse() {
            print("Parsed \(allNews.count) news for \(medium).")
        } else {
            print("Failed to parse XML for \(medium).")
        }
    }
}

extension ViewModel: XMLParserDelegate {
    /// Parses an XML element and processes its attributes and content.
    /// - Parameters:
    ///   - parser: The XML parser instance that is processing the data.
    ///   - elementName: The name of the current element being parsed.
    ///   - namespaceURI: The namespace URI associated with the element, if any.
    ///   - qualifiedName: The qualified name of the element (including namespace, if applicable).
    ///   - attributeDict: A dictionary containing the attributes of the element, with the attribute names as keys and their values as values.
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
    
    /// Processes the characters found within an XML element and updates the corresponding properties based on the element's name.
    /// - Parameters:
    ///   - parser: The XML parser instance that is processing the data.
    ///   - string: The string containing the characters found within the current XML element.
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
    
    /// Handles the end of an XML element and processes the data if the element is an "item".
    /// - Parameters:
    ///   - parser: The XML parser instance that is processing the data.
    ///   - elementName: The name of the element that has just ended.
    ///   - namespaceURI: The namespace URI associated with the element, if any.
    ///   - qualifiedName: The qualified name of the element (including namespace, if applicable).
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
