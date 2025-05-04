//
//  PressMedia.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 1/5/25.
//

import Foundation
import SwiftUICore

struct PressMedia: Codable, Equatable {
    let name: String
    let link: String
    
    static let mock = PressMedia(
        name: "El País",
        link: "https://www.elpais.com"
    )
}

enum Media: String, CaseIterable, Codable {
    case abc = "abc"
    case antena3 = "antena3"
    case cope = "cope"
    case diarioRed = "diarioRed"
    case elDiario = "elDiario"
    case elEconomista = "elEconomista"
    case elMundo = "elMundo"
    case elPais = "elPais"
    case elPeriodico = "elPeriodico"
    case elSalto = "elSalto"
    case esDiario = "esDiario"
    case expansion = "expansion"
    case laSexta = "laSexta"
    case laVanguardia = "laVanguardia"
    case libertadDigital = "libertadDigital"
    case rtve = "rtve"
    
    var pressMedia: PressMedia {
        switch self {
        case .abc: PressMedia(
            name: "ABC",
            link: "https://www.abc.es/rss/2.0/portada/"
        )
        case .antena3: PressMedia(
            name: "Antena 3",
            link: "https://www.antena3.com/noticias/rss/4013050.xml"
        )
        case .cope: PressMedia(
            name: "COPE",
            link: "https://www.cope.es/api/es/news/rss.xml"
        )
        case .diarioRed: PressMedia(
            name: "Diario Red",
            link: "https://www.diario-red.com/rss/"
        )
        case .elDiario: PressMedia(
            name: "El Diario",
            link: "https://www.eldiario.es/rss/"
        )
        case .elEconomista: PressMedia(
            name: "El Economista",
            link: "https://www.eleconomista.es/rss/rss-seleccion-ee.php"
        )
        case .elMundo: PressMedia(
            name: "El Mundo",
            link: "https://e00-elmundo.uecdn.es/elmundo/rss/portada.xml"
        )
        case .elPais: PressMedia(
            name: "El País",
            link: "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"
        )
        case .elPeriodico: PressMedia(
            name: "El Periódico",
            link: "https://www.elperiodico.com/es/cds/rss/?id=board.xml"
        )
        case .elSalto: PressMedia(
            name: "El Salto",
            link: "https://www.elsaltodiario.com/general/feed"
        )
        case .esDiario: PressMedia(
            name: "ES Diario",
            link: "https://www.esdiario.com/rss/home.xml"
        )
        case .expansion: PressMedia(
            name: "Expansión",
            link: "https://e00-expansion.uecdn.es/rss/portada.xml"
        )
        case .laSexta: PressMedia(
            name: "La Sexta",
            link: "https://www.lasexta.com/rss/351410.xml"
        )
        case .laVanguardia: PressMedia(
            name: "La Vanguardia",
            link: "https://www.lavanguardia.com/rss/home.xml"
        )
        case .libertadDigital: PressMedia(
            name: "Libertad Digital",
            link: "https://feeds2.feedburner.com/libertaddigital/portada"
        )
        case .rtve: PressMedia(
            name: "RTVE",
            link: "https://api2.rtve.es/rss/temas_noticias.xml"
        )
        }
    }
    
    static func from(_ rawValue: String) -> Media? {
        return Media(rawValue: rawValue)
    }
}

//extension String {
//    /// Normalizes the name of the media by converting it to lowercase, removing diacritical marks (accents),
//    /// replacing spaces with hyphens, and removing non-alphanumeric characters.
//    /// This is used to match the media name with the corresponding logo and color in the catalog.
//    ///
//    /// - Returns: A normalized version of the media name, in lowercase and without accents, spaces, or special characters.
//    func normalized() -> String {
//        return self
//            .lowercased()
//            .folding(options: .diacriticInsensitive, locale: .current)
//            .replacingOccurrences(of: " ", with: "-")
//            .filter { $0.isLetter || $0.isNumber || $0 == "-" }
//    }
//}

enum Category: String, CaseIterable, Decodable {
    case sinCategoria = "Sin categoría"
    case economia = "Economía"
    case politica = "Política"
    case ciencia = "Ciencia"
    case tecnologia = "Tecnología"
    case cultura = "Cultura"
    case sociedad = "Sociedad"
    case deportes = "Deportes"
    case internacional = "Internacional"
    case entretenimiento = "Entretenimiento"
    
    var systemImageName: String {
        switch self {
        case .sinCategoria: return "questionmark"
        case .economia: return "eurosign.circle"
        case .politica: return "building.columns"
        case .ciencia: return "atom"
        case .tecnologia: return "pc"
        case .cultura: return "book.pages"
        case .sociedad: return "person.2"
        case .deportes: return "sportscourt"
        case .internacional: return "globe"
        case .entretenimiento: return "popcorn"
        }
    }
}
