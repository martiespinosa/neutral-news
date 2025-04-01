//
//  NeutralNewsTests.swift
//  NeutralNewsTests
//
//  Created by Martí Espinosa Farran on 1/4/25.
//

import FirebaseAuth
import FirebaseFirestore
import Testing
@testable import NeutralNews

struct NeutralNewsTests {
    
    @Test func testInitialState() {
        let viewModel = ViewModel()
        #expect(viewModel.allNews.isEmpty)
        #expect(viewModel.filteredNews.isEmpty)
        #expect(viewModel.groupsOfNews.isEmpty)
        #expect(!viewModel.isAnyFilterEnabled)
    }
    
    @Test func testFetchingNews() async throws {
        let viewModel = ViewModel()
        
        // Simula la obtención de noticias en Firestore
        viewModel.allNews = [
            News(title: "News 1", description: "Desc", category: "Política", imageUrl: "", link: "", pubDate: "Mon, 25 Mar 2024 10:00:00 GMT", sourceMedium: .abc, group: 1),
            News(title: "News 2", description: "Desc", category: "Tech", imageUrl: "", link: "", pubDate: "Mon, 25 Mar 2024 12:00:00 GMT", sourceMedium: .elPais, group: nil)
        ]
        
        viewModel.applyFilters()
        
        #expect(viewModel.allNews.count == 2)
        #expect(viewModel.filteredNews.count == 2)
    }
    
    @Test func testFilteringByMedium() async throws {
        let viewModel = ViewModel()
        viewModel.allNews = [
            News(title: "News 1", description: "Desc", category: "Política", imageUrl: "", link: "", pubDate: "Mon, 25 Mar 2024 10:00:00 GMT", sourceMedium: .abc, group: 1),
            News(title: "News 2", description: "Desc", category: "Tecnología", imageUrl: "", link: "", pubDate: "Mon, 25 Mar 2024 12:00:00 GMT", sourceMedium: .elPais, group: nil)
        ]
        
        viewModel.filterByMedium(.abc)
        #expect(viewModel.filteredNews.count == 1)
        #expect(viewModel.filteredNews.first?.sourceMedium == .abc)
        
        viewModel.filterByMedium(.elPais) // Desactiva el filtro
        #expect(viewModel.filteredNews.count == 2)
    }
    
    @Test func testFilteringByCategory() async throws {
        let viewModel = ViewModel()
        viewModel.allNews = [
            News(title: "News 1", description: "Desc", category: "Política", imageUrl: "", link: "", pubDate: "Mon, 25 Mar 2024 10:00:00 GMT", sourceMedium: .abc, group: 1),
            News(title: "News 2", description: "Desc", category: "Tecnología", imageUrl: "", link: "", pubDate: "Mon, 25 Mar 2024 12:00:00 GMT", sourceMedium: .elPais, group: nil)
        ]
        
        viewModel.filterByCategory(.politica)
        #expect(viewModel.filteredNews.count == 1)
        #expect(viewModel.filteredNews.first?.category == "Política")
        
        viewModel.filterByCategory(.politica) // Desactiva el filtro
        #expect(viewModel.filteredNews.count == 2)
    }
}
