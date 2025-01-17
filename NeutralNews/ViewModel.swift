//
//  ViewModel.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 1/4/25.
//

import Foundation

@Observable
final class ViewModel: NSObject {
    var news = [News]()
    private var currentElement: String = ""
    private var currentTitle: String = ""
    private var currentDescription: String = ""
    private var currentCategory: String = ""
    private var currentImageUrl: String = ""
    private var currentLink: String = ""
    private var currentPubDate: String = ""
    private var currentMedium: Media?
    
    /// Loads data by fetching the RSS feed for each media item and parsing the XML data asynchronously.
    /// This function iterates through all available media types, fetches the data asynchronously,
    /// and processes it using the `parseXML` function.
    /// - Note: The function handles invalid URLs and errors during the data fetching process.
    /// - Important: If some RSS feeds fail to fetch, the process will continue for other media items without terminating.
    func loadData() async {
        for medium in Media.allCases {
            guard let url = URL(string: medium.pressMedia.link) else {
                print("Invalid URL")
                return
            }
            
            self.currentMedium = medium
            
            do {
                let (data, _) = try await URLSession.shared.data(from: url)
                parseXML(data: data, for: medium)
            } catch {
                print("Error fetching RSS feed: \(error.localizedDescription)")
            }
        }
    }
    
    /// Parses the provided XML data and processes it using the XMLParser.
    /// - Parameter data: The XML data to be parsed.
    private func parseXML(data: Data, for medium: Media) {
        let parser = XMLParser(data: data)
        parser.delegate = self
        if parser.parse() {
            print("Parsed \(news.count) news for \(medium).")
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
        
        if currentElement == "item" {
            currentTitle = ""
            currentDescription = ""
            currentCategory = ""
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
        let trimmedString = string.trimmingCharacters(in: .whitespacesAndNewlines)
        switch currentElement {
        case "title":
            currentTitle += trimmedString
        case "description":
            currentDescription += trimmedString
        case "category":
            currentCategory += trimmedString
        case "link":
            currentLink += trimmedString
        case "pubDate":
            currentPubDate += trimmedString
        default:
            break
        }
    }
    
    /// Handles the end of an XML element and processes the data if the element is an "item".
    /// - Parameters:
    ///   - parser: The XML parser instance that is processing the data.
    ///   - elementName: The name of the element that has just ended.
    ///   - namespaceURI: The namespace URI associated with the element, if any.
    ///   - qualifiedName: The qualified name of the element (including namespace, if applicable).
    func parser(_ parser: XMLParser, didEndElement elementName: String, namespaceURI: String?, qualifiedName: String?) {
        if elementName == "item", let medium = currentMedium {
            let newsItem = News(
                title: currentTitle,
                description: currentDescription,
                category: currentCategory != "" ? currentCategory : "Sin categoría",
                imageUrl: currentImageUrl,
                link: currentLink,
                pubDate: currentPubDate,
                sourceMedium: medium.pressMedia
            )
            
            if !news.contains(where: { $0.link == newsItem.link }) {
                news.append(newsItem)
            }
        }
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
