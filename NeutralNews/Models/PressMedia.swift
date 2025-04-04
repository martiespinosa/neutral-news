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
    case elMundo = "elMundo"
    case elPais = "elPais"
    case elPeriodico = "elPeriodico"
    case elSalto = "elSalto"
    case laVanguardia = "laVanguardia"
    case libertadDigital = "libertadDigital"
    case rtve = "rtve"
    
    var pressMedia: PressMedia {
        switch self {
        case .abc: PressMedia(
            name: "ABC",
            link: "https://www.abc.es/rss/2.0/portada/"
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
}

extension String {
    /// Normalizes the name of the media by converting it to lowercase, removing diacritical marks (accents),
    /// replacing spaces with hyphens, and removing non-alphanumeric characters.
    /// This is used to match the media name with the corresponding logo and color in the catalog.
    ///
    /// - Returns: A normalized version of the media name, in lowercase and without accents, spaces, or special characters.
    func normalized() -> String {
        return self
            .lowercased()
            .folding(options: .diacriticInsensitive, locale: .current)
            .replacingOccurrences(of: " ", with: "-")
            .filter { $0.isLetter || $0.isNumber || $0 == "-" }
    }
}

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
    case religion = "Religión"
}
