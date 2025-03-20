//
//  ViewModel.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 1/4/25.
//

import Foundation
import FirebaseAuth

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
        authenticateAnonymously()
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
                
                guard let token = token else {
                    print("No se pudo obtener un token válido")
                    return
                }
                
                print("Token obtenido correctamente: \(token)")
                Task {
                    await self.sendNewsToBackend(withToken: token)
                }
            }
        }
    }

    /// Función para enviar las noticias al backend.
    func sendNewsToBackend(withToken token: String) async {
        do {
            // Transformar las noticias al formato esperado por el backend
            let transformedNews = allNews.map { news in
                return [
                    "id": news.id.uuidString,
                    "titulo": news.title,
                    "cuerpo": news.description
                    // Añade otros campos si son necesarios para tu lógica de agrupación
                ]
            }
            
            let newsData = try JSONEncoder().encode(transformedNews)
            
            guard let url = URL(string: "https://us-central1-neutralnews-ca548.cloudfunctions.net/procesar_noticias") else {
                print("URL incorrecta")
                return
            }
            
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            request.httpBody = newsData
            
            // Realiza la solicitud HTTP
            let (data, response) = try await URLSession.shared.data(for: request)
            
            // Validar la respuesta HTTP
            guard let httpResponse = response as? HTTPURLResponse else {
                print("Respuesta inválida del servidor")
                return
            }
            
            // Si recibimos un error de autenticación, intentamos renovar el token
            if httpResponse.statusCode == 403 {
                print("Token expirado o inválido. Intentando renovar autenticación...")
                authenticateAnonymously() // Reautenticar
                return
            }
            
            guard (200...299).contains(httpResponse.statusCode) else {
                print("Error HTTP \(httpResponse.statusCode)")
                if let errorString = String(data: data, encoding: .utf8) {
                    print("Respuesta del servidor: \(errorString)")
                }
                return
            }
            
            // Intentar decodificar la respuesta JSON
            do {
                // Aquí hay que ajustar el tipo de decodificación según la respuesta del backend
                // El backend devuelve un objeto que incluye "group_number", necesitamos adaptarlo
                let decoder = JSONDecoder()
                
                struct BackendNews: Decodable {
                    let titulo: String
                    let cuerpo: String
                    let group_number: Int
                    // Añade otros campos que devuelve el backend
                }
                
                let backendResponse = try decoder.decode([BackendNews].self, from: data)
                
                // Convertir la respuesta del backend de nuevo a nuestro modelo News
                // y actualizar las noticias con sus grupos
                DispatchQueue.main.async {
                    // Aquí necesitarás mapear la respuesta del backend a tu modelo News
                    // y actualizar self.allNews con la información de grupos
                    print("Noticias agrupadas recibidas del backend: \(backendResponse.count)")
                    
                    // Ejemplo de cómo podrías actualizar tus noticias:
                    for (index, news) in self.allNews.enumerated() {
                        if let matchingBackendNews = backendResponse.first(where: { $0.titulo == news.title }) {
                            // Actualiza la noticia con su grupo
                            self.allNews[index].group = matchingBackendNews.group_number
                        }
                    }
                    
                    self.applyFilters()
                }
            } catch {
                print("Error al decodificar la respuesta del backend: \(error)")
                if let jsonString = String(data: data, encoding: .utf8) {
                    print("Respuesta del servidor: \(jsonString)")
                }
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
            let matchesCategory = categoryFilter.isEmpty || categoryFilter.contains { category in
                news.category.normalized() == category.rawValue.normalized()
            }
            
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
