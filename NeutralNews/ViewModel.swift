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
    private var currentLink: String = ""
    private var currentPubDate: String = ""
    private var currentMedium: Media?
    
    func loadData() async {
        for medium in Media.allCases {
            guard let url = URL(string: medium.pressMedia.link) else {
                print("Invalid URL")
                return
            }
            
            self.currentMedium = medium
            
            do {
                let (data, _) = try await URLSession.shared.data(from: url)
                parseXML(data: data)
            } catch {
                print("Error fetching RSS feed: \(error.localizedDescription)")
            }
        }
    }
    
    private func parseXML(data: Data) {
        let parser = XMLParser(data: data)
        parser.delegate = self
        if parser.parse() {
            print("Parsed \(news.count) news items")
        } else {
            print("Failed to parse XML")
        }
    }
}

extension ViewModel: XMLParserDelegate {
    func parser(_ parser: XMLParser, didStartElement elementName: String, namespaceURI: String?, qualifiedName: String?, attributes attributeDict: [String : String] = [:]) {
        currentElement = elementName
        if currentElement == "item" {
            currentTitle = ""
            currentDescription = ""
            currentCategory = ""
            currentLink = ""
            currentPubDate = ""
        }
    }
    
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
    
    func parser(_ parser: XMLParser, didEndElement elementName: String, namespaceURI: String?, qualifiedName: String?) {
        if elementName == "item", let medium = currentMedium {
            let newsItem = News(
                title: currentTitle,
                description: currentDescription,
                category: currentCategory,
                link: currentLink,
                pubDate: currentPubDate,
                sourceMedium: medium.pressMedia
            )
            news.append(newsItem)
        }
    }
}
